from odoo import _, fields, models


class SplitDeliveryTruckConfirmWizard(models.TransientModel):
    _name = "split.delivery.truck.confirm.wizard"
    _description = "Dividir traslado por camiones — paso 2: confirmación"

    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Recepción",
        required=True,
        readonly=True,
    )
    trucks_in_gate = fields.Integer(
        string="Camiones en caseta",
        readonly=True,
    )
    trucks_already_entered = fields.Integer(
        string="Camiones ya ingresados",
        readonly=True,
    )
    trucks_total = fields.Integer(
        string="Total de camiones",
        readonly=True,
    )
    confirmation_message = fields.Text(
        string="Confirmación",
        readonly=True,
    )

    def action_confirm_split(self):
        self.ensure_one()
        self.picking_id._split_truck_execute_split_by_truck_count(self.trucks_total)
        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
