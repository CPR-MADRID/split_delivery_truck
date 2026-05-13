import logging
import uuid
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    split_truck_parent_picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Recepción origen (división)",
        readonly=True,
        copy=False,
        index=True,
    )
    split_truck_child_picking_ids = fields.One2many(
        comodel_name="stock.picking",
        inverse_name="split_truck_parent_picking_id",
        string="Recepciones derivadas (división)",
        readonly=True,
        copy=False,
    )
    split_truck_total = fields.Integer(
        string="Total camiones (división)",
        readonly=True,
        copy=False,
    )
    split_truck_sequence = fields.Integer(
        string="Secuencia camión (división)",
        readonly=True,
        copy=False,
    )
    split_truck_group_ref = fields.Char(
        string="Referencia grupo división",
        readonly=True,
        copy=False,
        index=True,
    )
    split_truck_done = fields.Boolean(
        string="Dividido por camiones",
        readonly=True,
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Acción de botón — abre wizard paso 1
    # -------------------------------------------------------------------------

    def action_open_split_delivery_truck_wizard(self):
        self.ensure_one()
        self._split_truck_validate_can_open_split_wizard()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dividir traslado por camiones"),
            "res_model": "split.delivery.truck.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.id,
            },
        }

    # -------------------------------------------------------------------------
    # Conteo de visitantes Frontdesk
    # -------------------------------------------------------------------------

    def _split_truck_count_checked_in_visitors(self):
        self.ensure_one()
        return self.env["frontdesk.visitor"].search_count([
            ("state", "=", "checked_in"),
            ("picking_ids", "in", [self.id]),
        ])

    # -------------------------------------------------------------------------
    # Validaciones
    # -------------------------------------------------------------------------

    def _split_truck_validate_can_open_split_wizard(self):
        self.ensure_one()
        if self.picking_type_code != "incoming":
            raise UserError(_(
                "Solo se pueden dividir recepciones de tipo entrada (incoming). "
                "Esta recepción es de tipo '%(code)s'."
            ) % {"code": self.picking_type_code})
        if self.state in ("done", "cancel"):
            raise UserError(_(
                "No se puede dividir una recepción en estado '%(state)s'."
            ) % {"state": self.state})
        if not self.move_ids:
            raise UserError(_("La recepción no tiene movimientos de inventario."))

    def _split_truck_validate_can_split_by_truck(self, trucks_total):
        self.ensure_one()
        self._split_truck_validate_can_open_split_wizard()
        if trucks_total <= 1:
            raise UserError(_(
                "El total de camiones debe ser mayor a 1 para realizar una división. "
                "Total indicado: %(total)d."
            ) % {"total": trucks_total})
        blocked_moves = self.move_ids.filtered(lambda m: m.state in ("done", "cancel"))
        if blocked_moves:
            raise UserError(_(
                "No se puede dividir: existen movimientos en estado 'done' o 'cancel'."
            ))
        # picked=True en estado assigned/confirmed/waiting no indica recepción efectiva;
        # solo se bloquea por estado done/cancel (ya verificado arriba).
        # Solo bloquear por paquetes; qty_done y quantity se sincronizan tras la división
        for ml in self.move_line_ids:
            if ml.package_id or ml.result_package_id:
                raise UserError(_(
                    "No se puede dividir: hay líneas de operación con paquetes asignados."
                ))
        # Bloquear si algún move tiene más de una línea operativa con cantidad positiva
        for move in self.move_ids:
            positive_lines = move.move_line_ids.filtered(
                lambda ml: ml.quantity > 0 or ml.qty_done > 0
            )
            if len(positive_lines) > 1:
                raise UserError(_(
                    "No se puede dividir automáticamente: el movimiento del producto "
                    "'%(product)s' tiene múltiples líneas operativas con cantidad. "
                    "Limpie o simplifique las líneas antes de dividir."
                ) % {"product": move.product_id.display_name})
        if self._split_truck_has_processed_quality_checks():
            raise UserError(_(
                "No se puede dividir: hay controles de calidad procesados en esta recepción."
            ))
        # Bloquear si cualquier línea elegible tiene cantidad operativa editable <= 1
        for move in self.move_ids:
            op_qty = self._split_truck_get_operational_qty(move)
            if op_qty <= 1.0:
                raise UserError(_(
                    "En el movimiento de recepción %(picking)s existe una línea con "
                    "cantidad menor o igual a 1. Aumente la cantidad a recibir o "
                    "duplique la transferencia en lugar de dividirla."
                ) % {"picking": self.name})
        # Los registros de báscula no bloquean la división si el picking no está done/cancel
        # (ya validado en _split_truck_validate_can_open_split_wizard).
        # Los registros existentes permanecen en el picking original.

    # -------------------------------------------------------------------------
    # Verificaciones de calidad y báscula
    # -------------------------------------------------------------------------

    def _split_truck_has_processed_quality_checks(self):
        self.ensure_one()
        # Si el picking expone quality_check_done y está en False, la recepción aún no
        # completó calidad: no bloquear la división.
        if 'quality_check_done' in self._fields and not self.quality_check_done:
            return False
        # Estados que se consideran pendientes/no procesados — fácil de ajustar
        _PENDING_STATES = {False, "none", "todo"}
        checks = self.env["quality.check"].search([("picking_id", "=", self.id)])
        for check in checks:
            if check.quality_state not in _PENDING_STATES:
                return True
        return False

    def _split_truck_has_processed_scale_logs(self):
        # Mantenido por compatibilidad; ya no se invoca en _split_truck_validate_can_split_by_truck.
        self.ensure_one()
        _UNPROCESSED_STATES = {False, "draft", "cancel", "cancelled"}
        logs = self.env["stock.scale.log"].search([("picking_id", "=", self.id)])
        for log in logs:
            if log.state not in _UNPROCESSED_STATES:
                return True
        return False

    # -------------------------------------------------------------------------
    # Helper: cantidad operativa editable del movimiento (antes de validar)
    # -------------------------------------------------------------------------

    def _split_truck_get_operational_qty(self, move):
        """Return the editable operational qty for a move before picking validation.

        Prefers move.quantity (Odoo 18 operational field); falls back to the
        positive sum of move_line_ids.quantity.  Never reads product_uom_qty.
        """
        if 'quantity' in move._fields:
            qty = move.quantity
            if qty and qty > 0:
                return float(qty)
        return float(sum(ml.quantity for ml in move.move_line_ids if ml.quantity > 0))

    # -------------------------------------------------------------------------
    # Helper: sincronizar línea operativa del picking original tras dividir
    # -------------------------------------------------------------------------

    def _split_truck_sync_original_move_lines_after_split(self, move, target_qty):
        """Reduce quantity/qty_done en la única línea operativa del picking original."""
        self.ensure_one()
        lines = move.move_line_ids.filtered(lambda ml: ml.picking_id == self)
        if not lines:
            return

        if any(ml.package_id or ml.result_package_id for ml in lines):
            raise UserError(_(
                "No se puede sincronizar la línea operativa del producto '%(product)s': "
                "hay paquetes asignados en el picking original."
            ) % {"product": move.product_id.display_name})

        positive_lines = lines.filtered(lambda ml: ml.quantity > 0 or ml.qty_done > 0)
        if len(positive_lines) > 1:
            raise UserError(_(
                "No se puede sincronizar la línea operativa del producto '%(product)s': "
                "el movimiento tiene múltiples líneas con cantidad positiva. "
                "Limpie las líneas antes de dividir."
            ) % {"product": move.product_id.display_name})

        if not positive_lines:
            return

        main_line = positive_lines[0]

        # Convertir target_qty a la UoM de la línea si difiere de la del move
        target_qty_line_uom = target_qty
        if (main_line.product_uom_id and move.product_uom
                and main_line.product_uom_id != move.product_uom):
            target_qty_line_uom = move.product_uom._compute_quantity(
                target_qty, main_line.product_uom_id
            )

        ml_fields = self.env['stock.move.line']._fields
        write_vals = {}
        if 'quantity' in ml_fields:
            write_vals['quantity'] = target_qty_line_uom
        if 'qty_done' in ml_fields:
            write_vals['qty_done'] = target_qty_line_uom

        if write_vals:
            main_line.write(write_vals)

    # -------------------------------------------------------------------------
    # Cálculo de cantidades
    # -------------------------------------------------------------------------

    def _split_truck_compute_split_quantities(self, move, trucks_total):
        """Returns (qty_original, qty_per_child). Fixed 2-decimal precision. Residue to original.

        Uses Decimal arithmetic to avoid binary float drift.  Never reads
        product_uom.rounding or product_uom_qty.
        """
        total_qty = Decimal(str(self._split_truck_get_operational_qty(move)))
        precision = Decimal("0.01")
        child_count = Decimal(str(trucks_total - 1))

        child_qty = (total_qty / Decimal(str(trucks_total))).quantize(precision, rounding=ROUND_DOWN)

        if child_qty <= Decimal("0"):
            raise UserError(_(
                "La cantidad por camión para el producto '%(product)s' "
                "(%(qty)s / %(trucks)d camiones) es demasiado pequeña. No se puede dividir."
            ) % {
                "product": move.product_id.display_name,
                "qty": float(total_qty),
                "trucks": trucks_total,
            })

        original_qty = (total_qty - child_qty * child_count).quantize(precision, rounding=ROUND_HALF_UP)

        return float(original_qty), float(child_qty)

    # -------------------------------------------------------------------------
    # Preparación de valores
    # -------------------------------------------------------------------------

    def _split_truck_prepare_split_picking_vals(self, sequence, trucks_total, split_group_ref):
        self.ensure_one()
        vals = {
            "picking_type_id": self.picking_type_id.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "company_id": self.company_id.id,
            "split_truck_parent_picking_id": self.id,
            "split_truck_total": trucks_total,
            "split_truck_sequence": sequence,
            "split_truck_group_ref": split_group_ref,
        }
        if self.partner_id:
            vals["partner_id"] = self.partner_id.id
        if self.origin:
            vals["origin"] = self.origin
        if self.scheduled_date:
            vals["scheduled_date"] = self.scheduled_date
        if self.date_deadline:
            vals["date_deadline"] = self.date_deadline
        if self.group_id:
            vals["group_id"] = self.group_id.id
        if self.move_type:
            vals["move_type"] = self.move_type
        if self.purchase_id:
            vals["purchase_id"] = self.purchase_id.id
        return vals

    def _split_truck_prepare_split_move_vals(self, move, new_picking, quantity):
        vals = {
            "name": move.name,
            "picking_id": new_picking.id,
            "product_id": move.product_id.id,
            "product_uom": move.product_uom.id,
            "product_uom_qty": quantity,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
            "company_id": move.company_id.id,
            "picking_type_id": move.picking_type_id.id,
            "procure_method": move.procure_method,
        }
        if move.warehouse_id:
            vals["warehouse_id"] = move.warehouse_id.id
        if move.purchase_line_id:
            vals["purchase_line_id"] = move.purchase_line_id.id
        if move.group_id:
            vals["group_id"] = move.group_id.id
        if move.origin:
            vals["origin"] = move.origin
        if move.rule_id:
            vals["rule_id"] = move.rule_id.id
        return vals

    # -------------------------------------------------------------------------
    # Algoritmo principal de división
    # -------------------------------------------------------------------------

    def _split_truck_execute_split_by_truck_count(self, trucks_total):
        self.ensure_one()
        self._split_truck_validate_can_split_by_truck(trucks_total)

        original_moves = self.move_ids
        original_state = self.state

        # Snapshot de cantidad operativa original por (product_id, product_uom, purchase_line_id)
        original_snapshot = {}
        for move in original_moves:
            key = (move.product_id.id, move.product_uom.id, move.purchase_line_id.id)
            op_qty = self._split_truck_get_operational_qty(move)
            original_snapshot[key] = original_snapshot.get(key, 0.0) + op_qty

        # Pre-calcular cantidades para todos los movimientos antes de modificar nada
        split_qty_map = {}
        for move in original_moves:
            qty_original, qty_per_new = self._split_truck_compute_split_quantities(move, trucks_total)
            split_qty_map[move.id] = (qty_original, qty_per_new)

        split_group_ref = "SPLIT-%s-%s" % (self.name, uuid.uuid4().hex[:8].upper())

        # Reducir cantidades en los movimientos originales y sincronizar líneas operativas
        for move in original_moves:
            qty_original, _qty_per_new = split_qty_map[move.id]
            move.write({"product_uom_qty": qty_original})
            self._split_truck_sync_original_move_lines_after_split(move, qty_original)

        # Marcar picking original
        self.write({
            "split_truck_done": True,
            "split_truck_total": trucks_total,
            "split_truck_sequence": 1,
            "split_truck_group_ref": split_group_ref,
        })

        # Crear trucks_total - 1 pickings nuevos con sus movimientos
        new_pickings = self.env["stock.picking"]
        for seq in range(2, trucks_total + 1):
            picking_vals = self._split_truck_prepare_split_picking_vals(seq, trucks_total, split_group_ref)
            new_picking = self.env["stock.picking"].create(picking_vals)
            for move in original_moves:
                _qty_original, qty_per_new = split_qty_map[move.id]
                move_vals = self._split_truck_prepare_split_move_vals(move, new_picking, qty_per_new)
                self.env["stock.move"].create(move_vals)
            new_pickings |= new_picking

        # Confirmar nuevos pickings según estado del original
        if original_state in ("confirmed", "waiting", "assigned"):
            for np in new_pickings:
                np.action_confirm()

        # Intentar reservar; si falla se registra warning pero no interrumpe el split
        if original_state == "assigned":
            for np in new_pickings:
                try:
                    np.action_assign()
                except Exception:
                    _logger.warning(
                        "No se pudo reservar el picking %s durante la división por camiones.",
                        np.name,
                        exc_info=True,
                    )

        # Validar integridad antes de declarar éxito — rollback automático si falla
        self._split_truck_validate_split_total_integrity(original_snapshot, split_group_ref, trucks_total)

        self._split_truck_post_split_messages(new_pickings, trucks_total)

        return new_pickings

    # -------------------------------------------------------------------------
    # Validación de integridad post-split
    # -------------------------------------------------------------------------

    def _split_truck_validate_split_total_integrity(self, original_snapshot, split_group_ref, trucks_total):
        self.ensure_one()
        all_pickings = self.env["stock.picking"].search([
            ("split_truck_group_ref", "=", split_group_ref),
        ])
        if len(all_pickings) != trucks_total:
            raise UserError(_(
                "Error de integridad en la división: se esperaban %(expected)d recepciones "
                "en el grupo '%(ref)s', pero se encontraron %(found)d."
            ) % {
                "expected": trucks_total,
                "ref": split_group_ref,
                "found": len(all_pickings),
            })

        split_totals = {}
        for picking in all_pickings:
            for move in picking.move_ids:
                key = (move.product_id.id, move.product_uom.id, move.purchase_line_id.id)
                split_totals[key] = split_totals.get(key, 0.0) + move.product_uom_qty

        for key, original_qty in original_snapshot.items():
            split_qty = split_totals.get(key, 0.0)
            # Fixed 2-decimal precision: does not depend on product_uom.rounding
            if float_compare(split_qty, original_qty, precision_rounding=0.01) != 0:
                product = self.env["product.product"].browse(key[0])
                raise UserError(_(
                    "Error de integridad: la demanda total tras la división no coincide. "
                    "Producto: %s. Cantidad posterior: %.4f. Cantidad original: %.4f. "
                    "La operación fue cancelada."
                ) % (product.display_name, split_qty, original_qty))

    # -------------------------------------------------------------------------
    # Mensajes en chatter
    # -------------------------------------------------------------------------

    def _split_truck_post_split_messages(self, new_pickings, trucks_total):
        self.ensure_one()
        new_names = ", ".join(new_pickings.mapped("name"))
        self.message_post(
            body=_(
                "Recepción dividida por camiones. "
                "Total de camiones: %(total)d. "
                "Referencia de grupo: %(ref)s. "
                "Recepciones generadas: %(names)s."
            ) % {
                "total": trucks_total,
                "ref": self.split_truck_group_ref,
                "names": new_names,
            }
        )
        for np in new_pickings:
            np.message_post(
                body=_(
                    "Recepción creada como parte de una división por camiones "
                    "desde la recepción %(origin)s (referencia de grupo: %(ref)s)."
                ) % {
                    "origin": self.name,
                    "ref": self.split_truck_group_ref,
                }
            )
