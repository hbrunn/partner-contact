# -*- coding: utf-8 -*-
# © 2013-2016 Therp BV <http://therp.nl>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Define the type of relations that can exist between partners."""
from openerp import _, api, fields, models


class ResPartnerRelationType(models.Model):
    """Model that defines relation types that might exist between partners"""
    _name = 'res.partner.relation.type'
    _description = 'Partner Relation Type'
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    name_inverse = fields.Char(
        string='Inverse name',
        required=True,
        translate=True,
    )
    contact_type_left = fields.Selection(
        selection='get_partner_types',
        string='Left partner type',
    )
    contact_type_right = fields.Selection(
        selection='get_partner_types',
        string='Right partner type',
    )
    partner_category_left = fields.Many2one(
        comodel_name='res.partner.category',
        string='Left partner category',
    )
    partner_category_right = fields.Many2one(
        comodel_name='res.partner.category',
        string='Right partner category',
    )
    allow_self = fields.Boolean(
        string='Reflexive',
        help='This relation can be set up with the same partner left and '
        'right',
        default=False,
    )
    is_symmetric = fields.Boolean(
        string='Symmetric',
        old_name='symmetric',
        help="This relation is the same from right to left as from left to"
             " right",
        default=False,
    )

    @api.model
    def get_partner_types(self):
        """A partner can be an organisation or an individual."""
        # pylint: disable=no-self-use
        return [
            ('c', _('Organisation')),
            ('p', _('Person')),
        ]

    @api.onchange('is_symmetric')
    def onchange_is_symmetric(self):
        """Set right side to left side if symmetric."""
        if self.is_symmetric:
            self.update({
                'name_inverse': self.name,
                'contact_type_right': self.contact_type_left,
                'partner_category_right': self.partner_category_left,
            })
