# -*- coding: utf-8 -*-
# © 2014-2016 Therp BV <http://therp.nl>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from psycopg2.extensions import AsIs

from openerp import api, fields, models
from openerp.tools import drop_view_if_exists

from .res_partner_relation_type_selection import\
    ResPartnerRelationTypeSelection


PADDING = 10


class ResPartnerRelationAll(models.AbstractModel):
    _auto = False
    _log_access = False
    _name = 'res.partner.relation.all'
    _description = 'All (non-inverse + inverse) relations between partners'

    _overlays = 'res.partner.relation'

    _additional_view_fields = []
    """append to this list if you added fields to res_partner_relation that
    you need in this model and related fields are not adequate (ie for sorting)
    You must use the same name as in res_partner_relation.
    Don't overwrite this list in your declaration but append in _auto_init:

    def _auto_init(self, cr, context=None):
        self._additional_view_fields.append('my_field')
        return super(ResPartnerRelationAll, self)._auto_init(
            cr, context=context)

    my_field = fields...
    """

    this_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Current Partner',
        required=True,
    )
    other_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Other Partner',
        required=True,
    )
    type_id = fields.Many2one(
        comodel_name='res.partner.relation.type',
        string='Relation Type',
        required=True,
    )
    type_selection_id = fields.Many2one(
        comodel_name='res.partner.relation.type.selection',
        string='Relation Type',
        required=True,
    )
    relation_id = fields.Many2one(
        comodel_name='res.partner.relation',
        string='Relation',
        readonly=True,
    )
    record_type = fields.Selection(
        selection=ResPartnerRelationTypeSelection._RECORD_TYPES,
        string='Record Type',
        readonly=True,
    )
    date_start = fields.Date('Starting date')
    date_end = fields.Date('Ending date')
    active = fields.Boolean('Active', default=True)

    def _auto_init(self, cr, context=None):
        drop_view_if_exists(cr, self._table)
        additional_view_fields = ','.join(self._additional_view_fields)
        additional_view_fields = (',' + additional_view_fields)\
            if additional_view_fields else ''
        cr.execute(
            """create or replace view %(table)s as
            select
                id * %(padding)s as id,
                id as relation_id,
                type_id,
                cast('a' as char(1)) as record_type,
                left_partner_id as this_partner_id,
                right_partner_id as other_partner_id,
                date_start,
                date_end,
                active,
                type_id * %(padding)s as type_selection_id
                %(additional_view_fields)s
            from %(underlying_table)s
            union select
                id * %(padding)s + 1,
                id,
                type_id,
                cast('b' as char(1)),
                right_partner_id,
                left_partner_id,
                date_start,
                date_end,
                active,
                type_id * %(padding)s + 1
                %(additional_view_fields)s
            from %(underlying_table)s""",
            {
                'table': AsIs(self._table),
                'padding': PADDING,
                'additional_view_fields': AsIs(additional_view_fields),
                'underlying_table': AsIs('res_partner_relation'),
            }
        )
        return super(ResPartnerRelationAll, self)._auto_init(
            cr, context=context)

    @api.multi
    def _get_underlying_object(self):
        """Get the record on which this record is overlaid"""
        return self.env[self._overlays].browse(
            i / PADDING for i in self.ids)

    @api.multi
    def name_get(self):
        return {
            this.id: '%s %s %s' % (
                this.this_partner_id.name,
                this.type_selection_id.display_name,
                this.other_partner_id.name,
            )
            for this in self
        }

    @api.onchange('type_selection_id')
    def onchange_type_selection_id(self):
        """Add domain on other_partner_id according to category_other and
        contact_type_other"""
        domain = []
        if self.type_selection_id.contact_type_other:
            domain.append(
                ('is_company', '=',
                 self.type_selection_id.contact_type_other == 'c'))
        if self.type_selection_id.partner_category_other:
            domain.append(
                ('category_id', 'in',
                 self.type_selection_id.partner_category_other.ids))
        return {
            'domain': {
                'other_partner_id': domain,
            }
        }

    @api.onchange('this_partner_id')
    def onchange_this_partner_id(self):
        if not self.this_partner_id:
            return {'domain': {'type_selection_id': []}}
        return {
            'domain': {
                'type_selection_id': [
                    '|',
                    ('contact_type_this', '=', False),
                    ('contact_type_this', '=',
                     self.this_partner_id.get_partner_type()),
                    '|',
                    ('partner_category_this', '=', False),
                    ('partner_category_this', 'in',
                     self.this_partner_id.category_id.ids),
                ],
            },
        }

    @api.model
    def get_type_from_selection_id(self, selection_type_id):
        """Return tuple with type_id and reverse indication for
        selection_type_id."""
        selection_model = self.env['res.partner.relation.type.selection']
        selection = selection_model.browse(selection_type_id)
        return selection.get_type_from_selection_id()

    @api.model
    def _correct_vals(self, vals):
        """Fill left and right partner from this and other partner."""
        vals = vals.copy()
        if 'this_partner_id' in vals:
            vals['left_partner_id'] = vals['this_partner_id']
            del vals['this_partner_id']
        if 'other_partner_id' in vals:
            vals['right_partner_id'] = vals['other_partner_id']
            del vals['other_partner_id']
        if 'type_selection_id' not in vals:
            return vals
        type_id, is_reverse = self.get_type_from_selection_id(
            vals['type_selection_id']
        )
        vals['type_id'] = type_id
        # Need to switch right and left partner if we are in reverse id:
        if 'left_partner_id' in vals or 'right_partner_id' in vals:
            if is_reverse:
                left_partner_id = False
                right_partner_id = False
                if 'left_partner_id' in vals:
                    right_partner_id = vals['left_partner_id']
                    del vals['left_partner_id']
                if 'right_partner_id' in vals:
                    left_partner_id = vals['right_partner_id']
                    del vals['right_partner_id']
                if left_partner_id:
                    vals['left_partner_id'] = left_partner_id
                if right_partner_id:
                    vals['right_partner_id'] = right_partner_id
        return vals

    @api.multi
    def write(self, vals):
        """divert non-problematic writes to underlying table"""
        underlying_objs = self._get_underlying_object()
        vals = {
            key: val
            for key, val in vals.iteritems()
            if not self._fields[key].readonly
        }
        vals = self._correct_vals(vals)
        return underlying_objs.write(vals)

    @api.model
    def create(self, vals):
        """divert non-problematic creates to underlying table

        Create a res.partner.relation but return the converted id
        """
        is_reverse = False
        if 'type_selection_id' in vals:
            relation_model = self.env['res.partner.relation']
            type_id, is_reverse = relation_model.get_type_from_selection_id(
                vals['type_selection_id']
            )
        vals = {
            key: val
            for key, val in vals.iteritems()
            if not self._fields[key].readonly
        }
        vals = self._correct_vals(vals)
        res = self.env[self._overlays].create(vals)
        return_id = res.id * PADDING + (is_reverse and 1 or 0)
        return self.browse(return_id)

    @api.multi
    def unlink(self):
        """divert non-problematic creates to underlying table"""
        return self._get_underlying_object().unlink()
