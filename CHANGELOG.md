# CHANGELOG

## 18.0.1.0.5 - 2026-05-25

### Fixed
- Quality checks ejecutados ya **no bloquean** la división de recepciones. La función
  `_split_truck_has_processed_quality_checks()` se usa únicamente como aviso informativo
  en el wizard de confirmación, nunca como bloqueo de validación.
- La división usa `stock.move.product_uom_qty` como base canónica del cálculo, en lugar
  de la cantidad operativa editable (`move.quantity`). Esto garantiza coherencia entre la
  demanda declarada y las cantidades distribuidas entre camiones.
- El snapshot de integridad pre-split ahora suma `product_uom_qty` de cada movimiento,
  consistente con la base canónica de cálculo.

### Changed
- `_split_truck_validate_can_split_by_truck`: eliminado el bloqueo por quality checks
  procesados y la validación previa de múltiples líneas positivas por movimiento (se
  mantiene en `_split_truck_sync_original_move_lines_after_split`). El bloqueo por
  `product_uom_qty <= 1.0` ahora lee directamente `move.product_uom_qty`.
- `_split_truck_compute_split_quantities`: cambia base de `_split_truck_get_operational_qty`
  a `move.product_uom_qty`; docstring actualizado.
- `_split_truck_get_operational_qty`: docstring actualizado con nota sobre base canónica
  v18.0.1.0.5; método conservado por compatibilidad con llamadas externas.
- `_split_truck_execute_split_by_truck_count`: snapshot usa `move.product_uom_qty`.
- `__manifest__.py`: versión `18.0.1.0.5`, categoría `Inventory/Inventory`, summary en español.
- `wizards/split_delivery_truck_wizard.py`: `action_confirm` muestra aviso informativo
  diferenciado cuando existen quality checks ejecutados; formato de mensaje con parámetros
  nombrados.

### Added
- Método `_split_truck_ensure_quality_checks_for_children(new_pickings)`: safety net que
  genera quality checks pendientes en pickings hijos si no fueron creados durante
  `action_confirm()` o `action_assign()`. No duplica checks existentes.

## 18.0.1.0.4 - 2026-05-12

### Fixed
- División de recepciones WH/IN ahora usa **cantidad operativa editable** (`move.quantity`)
  como base del cálculo, no `product_uom_qty`.
- Cálculo de cantidades con precisión fija de **2 decimales** (Decimal aritmético),
  sin depender de `product_uom.rounding`.
- **Residuo** de la división se asigna siempre al traslado original.
- Bloqueo de división cuando cualquier línea elegible tiene cantidad operativa **<= 1**,
  con el mensaje aprobado:
  *"En el movimiento de recepción [WH/IN/...] existe una línea con cantidad menor o igual a 1.
  Aumente la cantidad a recibir o duplique la transferencia en lugar de dividirla."*

### Changed
- `_split_truck_compute_split_quantities`: usa `Decimal` con `ROUND_DOWN` para `child_qty`
  y `ROUND_HALF_UP` para `original_qty`; no usa `float_round` ni `product_uom.rounding`.
- `_split_truck_validate_can_split_by_truck`: agrega bloqueo si cualquier línea tiene
  cantidad operativa editable <= 1.
- `_split_truck_execute_split_by_truck_count`: snapshot y cálculo basados en cantidad
  operativa editable (`_split_truck_get_operational_qty`).
- `_split_truck_validate_split_total_integrity`: comparación de integridad con
  `precision_rounding=0.01` fijo, sin consultar `uom.rounding`.

### Added
- Helper `_split_truck_get_operational_qty(move)`: extrae cantidad operativa editable
  preferiendo `move.quantity`; fallback a suma positiva de `move_line_ids.quantity`.

## 18.0.1.0.3 - 2026-05-11

### Changed
- Se publicó la versión `18.0.1.0.3`.
- Se permitió volver a dividir recepciones entrantes por camiones.
- Se mantuvieron los campos de trazabilidad de la división por camión.
- La división toma como base la cantidad vigente del picking seleccionado.

### Release
- Tag: `split_delivery_truck-18.0.1.0.3`