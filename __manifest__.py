{
    "name": "split_delivery_truck",
    "version": "18.0.1.0.5",
    "category": "Inventory/Inventory",
    "summary": "Divide recepciones WH/IN en partes proporcionales al número de camiones",
    "author": "Axxen Consulting",
    "license": "Other proprietary",
    "depends": [
        "stock",
        "purchase",
        "purchase_stock",
        "purchase_delivery_split_date",
        "frontdesk",
        "frontdesk_stock",
        "frontdesk_stock_scale",
        "frontdesk_quality",
        "stock_location_history",
        "stock_scale",
        "quality",
        "quality_control"
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/split_delivery_truck_wizard_views.xml",
        "wizards/split_delivery_truck_confirm_wizard_views.xml",
        "views/stock_picking_views.xml"
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}