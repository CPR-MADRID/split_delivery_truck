from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SplitDeliveryTruckWizard(models.TransientModel):
    _name = "split.delivery.truck.wizard"
    _description = "Dividir traslado por camiones — paso 1: captura"

    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Recepción",
        required=True,
        readonly=True,
    )
    trucks_in_gate = fields.Integer(
        string="Camiones en caseta",
        required=True,
        default=0,
    )
    trucks_already_entered = fields.Integer(
        string="Camiones ya ingresados",
        readonly=True,
    )
    trucks_total = fields.Integer(
        string="Total de camiones",
        readonly=True,
    )
    message = fields.Text(
        string="Información",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking_id = res.get("picking_id") or self.env.context.get("default_picking_id")
        if picking_id:
            picking = self.env["stock.picking"].browse(picking_id)
            already = picking._split_truck_count_checked_in_visitors()
            res["trucks_already_entered"] = already
            res["trucks_total"] = already
            res["message"] = _(
                "Hay %d camión(es) ya ingresado(s) para esta recepción. "
                "Capture los camiones actualmente en caseta para calcular el total."
            ) % already
        return res

    @api.onchange("trucks_in_gate")
    def _onchange_trucks_in_gate(self):
        in_gate = self.trucks_in_gate or 0
        already = self.trucks_already_entered or 0
        total = in_gate + already
        self.trucks_total = total
        self.message = _(
            "Hay %(entered)d camión(es) ingresado(s) para esta recepción. "
            "El total de camiones para esta entrega será de %(total)d."
        ) % {"entered": already, "total": total}

    def action_confirm(self):
        self.ensure_one()
        if not self.trucks_in_gate or self.trucks_in_gate <= 0:
            raise UserError(_("Debe capturar al menos 1 camión en caseta."))
        # Recalcular al momento de confirmar para evitar datos desactualizados
        already = self.picking_id._split_truck_count_checked_in_visitors()
        trucks_total = self.trucks_in_gate + already
        # Mostrar aviso especial si hay quality checks ejecutados en el picking original
        if self.picking_id._split_truck_has_processed_quality_checks():
            confirmation_message = _(
                "El movimiento tiene checks de calidad ejecutados. "
                "La recepción se dividirá de manera equitativa; los checks existentes "
                "permanecerán asociados a la transferencia original y las nuevas "
                "transferencias deberán generar sus propios checks de calidad pendientes. "
                "¿Quiere continuar?"
            )
        else:
            confirmation_message = _(
                "Estás por dividir la recepción %(picking)s en %(total)d parte(s) iguales. "
                "¿Quieres confirmar?"
            ) % {"picking": self.picking_id.name, "total": trucks_total}
        return {
            "type": "ir.actions.act_window",
            "name": _("Confirmar división por camiones"),
            "res_model": "split.delivery.truck.confirm.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.picking_id.id,
                "default_trucks_in_gate": self.trucks_in_gate,
                "default_trucks_already_entered": already,
                "default_trucks_total": trucks_total,
                "default_confirmation_message": confirmation_message,
            },
        }
