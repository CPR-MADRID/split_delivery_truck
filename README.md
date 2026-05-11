# split_delivery_truck

## Propósito

El módulo `split_delivery_truck` permite dividir una recepción entrante de inventario en varios traslados proporcionales, tomando como base el número de camiones capturados por el usuario.

Su objetivo funcional es facilitar la operación logística cuando una misma recepción debe separarse en varios traslados relacionados con distintos camiones, conservando la proporcionalidad de las cantidades originales.

## Alcance funcional

El módulo opera sobre recepciones de inventario de Odoo, principalmente traslados de entrada tipo WH/IN.

La funcionalidad permite:

- Abrir un asistente desde el traslado.
- Capturar el número total de camiones.
- Calcular cantidades proporcionales por traslado.
- Conservar una parte proporcional en el picking original.
- Crear nuevos pickings proporcionales para los camiones adicionales.
- Mantener la suma total posterior igual a la cantidad original.

## Modelo principal afectado

- `stock.picking`

## Componentes técnicos

El módulo incluye:

- Extensión de `stock.picking`.
- Wizard principal para capturar número de camiones.
- Wizard de confirmación.
- Vistas XML para botón y asistentes.
- Reglas de acceso para modelos transitorios.
- Validaciones funcionales para evitar divisiones inseguras.

## Reglas funcionales principales

El módulo bloquea la división cuando existen condiciones de riesgo operativo o técnico, incluyendo:

- Traslados en estado `done`.
- Traslados en estado `cancel`.
- Operaciones con paquetes.
- Estructuras de líneas no soportadas por la versión actual.
- Condiciones donde la calidad ya fue procesada.
- Casos donde dividir el traslado podría comprometer trazabilidad o consistencia.

El estado `assigned` se considera una recepción disponible/preparada, no una recepción validada. Por lo tanto, no debe bloquearse únicamente por encontrarse en estado `assigned`.

## Criterio de proporcionalidad

Si una recepción tiene una cantidad total y el usuario solicita dividirla entre N camiones, el módulo conserva en el traslado original una fracción proporcional y genera N-1 nuevos traslados con cantidades proporcionales.

Ejemplo:

Cantidad original: 10  
Número de camiones: 5  

Resultado esperado:

- Picking original: 2
- Picking nuevo 1: 2
- Picking nuevo 2: 2
- Picking nuevo 3: 2
- Picking nuevo 4: 2

Total posterior: 10

## Dependencias

El módulo depende de funcionalidades de inventario, compras, recepción, frontdesk, báscula, calidad y control de ubicación requeridas por el flujo operativo.

Dependencias declaradas en `__manifest__.py`:

- `stock`
- `purchase`
- `purchase_stock`
- `purchase_delivery_split_date`
- `frontdesk`
- `frontdesk_stock`
- `frontdesk_stock_scale`
- `frontdesk_quality`
- `stock_location_history`
- `stock_scale`
- `quality`
- `quality_control`

## Restricción de instalación

Este módulo no debe instalarse en una base donde ya exista otra variante activa que implemente la misma lógica sobre `stock.picking`, botones equivalentes, campos equivalentes o vistas equivalentes, salvo que exista un plan formal de sustitución.

Antes de instalarlo, se debe validar:

- Que no exista duplicidad de botones.
- Que no exista duplicidad de vistas heredadas.
- Que no exista duplicidad de campos.
- Que no exista duplicidad de métodos.
- Que el módulo anterior haya sido desinstalado, desactivado o sustituido de forma controlada.

## Estado actual

Versión: `18.0.1.0.3`  
Nombre técnico: `split_delivery_truck`  
Categoría: `Inventory`  
Licencia: `Other proprietary`  

## Política de desarrollo

Este módulo debe mantenerse como módulo independiente, plug in / plug out, sin modificar Odoo core, Odoo Enterprise, OCA ni módulos externos no autorizados.

Cualquier ajuste futuro debe realizarse de forma versionada, documentada, probada y validada antes de avanzar a ambientes superiores.
