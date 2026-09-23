"""Business validation of the versioned, JSON-compatible calculation dataset."""

import calendar
import math
from datetime import date


def issue(code, severity, message, **context):
    """Keep a stable, machine-readable location even when a field is unavailable."""
    return {
        "code": code,
        "severity": severity,
        "message": message,
        **{key: context.get(key) for key in ("source", "sheet", "row", "sku", "field")},
    }


def make_report(issues, *, products=0, **summary):
    errors = [item["message"] for item in issues if item["severity"] == "error"]
    warnings = [item["message"] for item in issues if item["severity"] == "warning"]
    return {
        "valid": not errors,
        "business_validation": "failed" if errors else "passed",
        "errors": list(dict.fromkeys(errors)),
        "warnings": list(dict.fromkeys(warnings)),
        "summary": {"products": products, **summary, "issues": issues},
    }


def _finite_number(value):
    try:
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        )
    except OverflowError:
        return False


def validate_dataset(payload):
    """Return a report, without repairing data or substituting missing values."""
    issues = []

    def add(code, severity, message, sku=None, field=None, row=None):
        prefix = f"SKU {sku}: " if sku else ""
        issues.append(issue(code, severity, prefix + message, sku=sku, field=field, row=row))

    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        add("invalid_schema", "error", "Ожидается схема данных версии 1.")
        return make_report(issues)
    source_issues = payload.get("validation_issues", [])
    if not isinstance(source_issues, list):
        add("invalid_source_issues", "error", "Ошибки источников должны быть списком.")
        source_issues = []
    for item in source_issues:
        if isinstance(item, dict) and item.get("severity") in ("error", "warning"):
            issues.append(
                issue(
                    str(item.get("code", "source_validation")),
                    item["severity"],
                    str(item.get("message", "Ошибка источника.")),
                    **{key: item.get(key) for key in ("source", "sheet", "row", "sku", "field")},
                )
            )
    products = payload.get("products")
    if not isinstance(products, list) or not products:
        add("empty_products", "error", "В наборе нет товаров.", field="products")
        return make_report(issues)

    def numeric(value, sku, field, *, positive=False, integer=False):
        if value is None:
            return False
        if not _finite_number(value):
            add("invalid_number", "error", f"Поле {field} должно быть конечным числом.", sku, field)
            return False
        if value < 0 or (positive and value == 0):
            sign = "положительным" if positive else "неотрицательным"
            add("invalid_range", "error", f"Поле {field} должно быть {sign}.", sku, field)
            return False
        if integer and value != int(value):
            add("invalid_integer", "error", f"Поле {field} должно быть целым.", sku, field)
            return False
        return True

    seen = set()
    for index, product in enumerate(products, 1):
        if not isinstance(product, dict):
            add("invalid_product", "error", "Строка товара должна быть объектом.", row=index)
            continue
        raw_sku = product.get("sku")
        sku = raw_sku if isinstance(raw_sku, str) else None
        for field in ("sku", "name", "supplier"):
            value = product.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                add("missing_required_field", "error", f"Не заполнено поле {field}.", sku, field)
        if sku in seen and sku is not None:
            add("duplicate_sku", "error", "Повторный SKU в нормализованных товарах.", sku, "sku")
        seen.add(sku)
        for field in ("stock", "moq", "order_multiple", "lead_time_days"):
            value = product.get(field)
            if value is None:
                add("missing_optional_field", "warning", f"Неизвестно поле {field}.", sku, field)
            elif (
                numeric(
                    value,
                    sku,
                    field,
                    positive=field == "order_multiple",
                    integer=field == "lead_time_days",
                )
                and field == "lead_time_days"
                and value > 3650
            ):
                add("invalid_range", "error", "Срок поставки превышает 3650 дней.", sku, field)
        unit = product.get("unit")
        if unit is None or unit == "":
            add("missing_unit", "warning", "Неизвестна единица измерения.", sku, "unit")
        elif not isinstance(unit, str) or len(unit) > 500:
            add("invalid_unit", "error", "Единица измерения должна быть текстом.", sku, "unit")

        sales = product.get("sales", [])
        if not isinstance(sales, list):
            add("invalid_sales", "error", "История продаж должна быть списком.", sku, "sales")
            sales = []
        if not sales:
            add("missing_history", "warning", "Нет истории продаж; спрос неизвестен.", sku, "sales")
        months = set()
        for sale in sales:
            if not isinstance(sale, dict):
                add("invalid_sales", "error", "Запись продаж должна быть объектом.", sku, "sales")
                continue
            month = None
            try:
                month = date.fromisoformat(sale.get("month"))
                if month.day != 1:
                    raise ValueError("not a month start")
            except (TypeError, ValueError):
                add("invalid_date", "error", "Месяц продаж должен быть YYYY-MM-01.", sku, "month")
            if month in months and month is not None:
                add("duplicate_sales", "error", "Продажи за месяц указаны повторно.", sku, "month")
            months.add(month)
            quantity = sale.get("quantity")
            if quantity is None:
                add(
                    "missing_sales_quantity",
                    "warning",
                    "Объём продаж за месяц неизвестен.",
                    sku,
                    "sales.quantity",
                )
            else:
                numeric(quantity, sku, "sales.quantity")
            days = sale.get("stockout_days")
            if days is not None and numeric(days, sku, "stockout_days", integer=True):
                if month and days > calendar.monthrange(month.year, month.month)[1]:
                    add(
                        "invalid_stockout_days",
                        "error",
                        "Дни отсутствия превышают длину месяца.",
                        sku,
                        "stockout_days",
                    )
                elif month and days == calendar.monthrange(month.year, month.month)[1]:
                    if _finite_number(quantity) and quantity > 0:
                        add(
                            "contradictory_stockout",
                            "error",
                            "Есть продажи при отсутствии товара весь месяц.",
                            sku,
                            "stockout_days",
                        )

        incoming = product.get("incoming", [])
        known = product.get("incoming_known", False)
        if not isinstance(known, bool):
            add(
                "invalid_incoming_known",
                "error",
                "incoming_known должен быть логическим.",
                sku,
                "incoming_known",
            )
        if not isinstance(incoming, list):
            add("invalid_incoming", "error", "Поставки должны быть списком.", sku, "incoming")
            incoming = []
        complete = True
        deliveries = set()
        for delivery in incoming:
            if not isinstance(delivery, dict):
                add("invalid_incoming", "error", "Поставка должна быть объектом.", sku, "incoming")
                complete = False
                continue
            quantity = delivery.get("quantity")
            if quantity is None:
                complete = False
            else:
                numeric(quantity, sku, "incoming.quantity")
            delivery_date = delivery.get("date")
            if delivery_date is None:
                if quantity != 0:
                    complete = False
            else:
                try:
                    date.fromisoformat(delivery_date)
                except (TypeError, ValueError):
                    complete = False
                    add(
                        "invalid_date",
                        "error",
                        "Дата поставки должна быть YYYY-MM-DD.",
                        sku,
                        "incoming.date",
                    )
            if _finite_number(quantity) and quantity > 0 and isinstance(delivery_date, str):
                key = (delivery_date, quantity)
                if key in deliveries:
                    add(
                        "ambiguous_duplicate_incoming",
                        "error",
                        "Повторная поставка с той же датой и объёмом: "
                        "уточните, это дубль или отдельный заказ.",
                        sku,
                        "incoming",
                    )
                deliveries.add(key)
        if known is True and not complete:
            add(
                "inconsistent_incoming",
                "error",
                "Поставки отмечены известными при неполных данных.",
                sku,
                "incoming_known",
            )
        if known is not True:
            add(
                "missing_incoming",
                "warning",
                "Объём или даты ожидаемых поставок неизвестны.",
                sku,
                "incoming",
            )

        seasonality = product.get("seasonality", {})
        if not isinstance(seasonality, dict):
            add(
                "invalid_seasonality",
                "error",
                "Сезонность должна быть словарём месяцев.",
                sku,
                "seasonality",
            )
        else:
            for month, coefficient in seasonality.items():
                if month not in {str(value) for value in range(1, 13)}:
                    add(
                        "invalid_seasonality_month",
                        "error",
                        "Месяц сезонности должен быть 1..12.",
                        sku,
                        "seasonality",
                    )
                if coefficient is None:
                    add(
                        "missing_seasonality_value",
                        "warning",
                        "Коэффициент сезонности неизвестен.",
                        sku,
                        "seasonality",
                    )
                else:
                    numeric(coefficient, sku, "seasonality", positive=True)
    return make_report(issues, products=len(products))
