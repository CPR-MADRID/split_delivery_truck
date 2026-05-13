# CHANGELOG

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