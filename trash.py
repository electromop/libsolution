from fastapi import Body
from sqlalchemy import and_, func
from typing import Dict, Any

@app.post("/items/filter", response_model=List[ItemOut])
def filter_items(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    """w
    Фильтрация items по сложному payload фильтров.
    """
    filters = payload
    query = db.query(SubstanceItem)
    conditions = []

    # Фильтр по имени
    name_mode = filters.get("name_mode")
    name_value = filters.get("name")
    if name_value is not None and name_mode:
        if name_mode == "contains":
            conditions.append(func.lower(SubstanceItem.name).ilike(f"%{name_value.lower()}%"))
        elif name_mode == "equals":
            conditions.append(func.lower(SubstanceItem.name) == name_value.lower())

    # Фильтр по created_at (дата от/до)
    created_at_from = filters.get("field_created_at_date_from")
    created_at_to = filters.get("field_created_at_date_to")
    if created_at_from:
        try:
            dt_from = datetime.fromisoformat(created_at_from)
            conditions.append(SubstanceItem.created_at >= dt_from)
        except Exception:
            pass
    if created_at_to:
        try:
            dt_to = datetime.fromisoformat(created_at_to)
            conditions.append(SubstanceItem.created_at <= dt_to)
        except Exception:
            pass

    # Фильтры по полям data
    for key, value in filters.items():
        if not key.startswith("field_"):
            continue
        # Пропускаем created_at, его уже обработали
        if key.startswith("field_created_at"):
            continue

        # Пример: field_Масса_from, field_Масса_to, field_Опасносить_mode, field_поле 3_mode
        if key.endswith("_from"):
            field_name = key[6:-5]
            try:
                val = float(value)
                # SQLite: json_extract(data, '$."Масса"') >= val
                conditions.append(func.json_extract(SubstanceItem.data, f'$.\"{field_name}\"') >= val)
            except Exception:
                pass
        elif key.endswith("_to"):
            field_name = key[6:-3]
            try:
                val = float(value)
                conditions.append(func.json_extract(SubstanceItem.data, f'$.\"{field_name}\"') <= val)
            except Exception:
                pass
        elif key.endswith("_mode"):
            # обработаем ниже вместе с соответствующим значением
            continue
        else:
            # Это может быть строковое значение для поиска по полю
            field_name = key[6:]
            mode = filters.get(f"field_{field_name}_mode")
            if value is not None and mode:
                json_path = f'$.\"{field_name}\"'
                if mode == "contains":
                    conditions.append(
                        func.lower(func.json_extract(SubstanceItem.data, json_path)).ilike(f"%{str(value).lower()}%")
                    )
                elif mode == "equals":
                    conditions.append(
                        func.lower(func.json_extract(SubstanceItem.data, json_path)) == str(value).lower()
                    )

    if conditions:
        query = query.filter(and_(*conditions))
    return query.all()