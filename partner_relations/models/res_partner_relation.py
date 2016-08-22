# -*- coding: utf-8 -*-
# © 2013-2016 Therp BV <http://therp.nl>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openerp import _, api, exceptions, fields, models
from openerp.osv.expression import TRUE_LEAF


class ResPartnerRelation(models.Model):
    """Model res.partner.relation is used to describe all links or relations
    between partners in the database.

    In many parts of the code we have to know whether the active partner is
    the left partner, or the right partner. If the active partner is the
    right partner we have to show the inverse name.

    Because the active partner is crucial for the working of partner
    relationships, we make sure on the res.partner model that the partner id
    is set in the context where needed.
    """
    _name = 'res.partner.relation'
    _description = 'Partner relation'
    _order = 'left_partner_id, active desc, date_start desc, date_end desc'

    allow_self = fields.Boolean(related='type_id.allow_self')
    any_partner_id = fields.Many2many(
        comodel_name='res.partner',
        string='Partner',
        compute='_compute_any_partner_id',
        search='_search_any_partner_id'
    )
    left_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Source Partner',
        required=True,
        auto_join=True,
        ondelete='cascade',
    )
    right_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Destination Partner',
        required=True,
        auto_join=True,
        ondelete='cascade',
    )
    type_id = fields.Many2one(
        comodel_name='res.partner.relation.type',
        string='Type',
        required=True,
        auto_join=True,
    )
    date_start = fields.Date('Starting date')
    date_end = fields.Date('Ending date')
    active = fields.Boolean('Active', default=True)

    @api.onchange(
        'left_partner_id',
        'right_partner_id',
        'type_id',
    )
    def _onchange_type_or_partner(self):
        """Set domain on input fields depending on value of other fields.

        Selecting a left or right partner, or a relation type will limit the
        choices for the other fields.
        """
        left_partner_domain = []
        right_partner_domain = []
        type_domain = []
        # Build left and right partner domains from type_id
        if self.type_id:
            if self.type_id.contact_type_left:
                check_contact_type = self.type_id.contact_type_left
                if check_contact_type == 'c':
                    left_partner_domain.append(('is_company', '=', True))
                if check_contact_type == 'p':
                    left_partner_domain.append(('is_company', '=', False))
            if self.type_id.partner_category_left:
                check_partner_category = self.type_id.partner_category_left
                left_partner_domain.append(
                    ('category_id', 'child_of', check_partner_category.ids)
                )
            if self.type_id.contact_type_right:
                check_contact_type = self.type_id.contact_type_right
                if check_contact_type == 'c':
                    right_partner_domain.append(('is_company', '=', True))
                if check_contact_type == 'p':
                    right_partner_domain.append(('is_company', '=', False))
            if self.type_id.partner_category_right:
                check_partner_category = self.type_id.partner_category_right
                right_partner_domain.append(
                    ('category_id', 'child_of', check_partner_category.ids)
                )
        # Build selection domain from partner info
        if self.left_partner_id:
            if self.left_partner_id.is_company:
                type_domain += [
                    '|',
                    ('contact_type_left', '=', False),
                    ('contact_type_left', '=', 'c')
                ]
            else:
                type_domain += [
                    '|',
                    ('contact_type_left', '=', False),
                    ('contact_type_left', '=', 'p')
                ]
            type_domain += [
                '|',
                ('partner_category_left', '=', False),
                ('partner_category_left',
                 'in',
                 self.left_partner_id.category_id.ids
                )
            ]
        if self.right_partner_id:
            if self.right_partner_id.is_company:
                type_domain += [
                    '|',
                    ('contact_type_right', '=', False),
                    ('contact_type_right', '=', 'c')
                ]
            else:
                type_domain += [
                    '|',
                    ('contact_type_right', '=', False),
                    ('contact_type_right', '=', 'p')
                ]
            type_domain += [
                '|',
                ('partner_category_right', '=', False),
                ('partner_category_right',
                 'in',
                 self.right_partner_id.category_id.ids
                )
            ]
        domain = {
            'left_partner_id': left_partner_domain,
            'right_partner_id': right_partner_domain,
            'type_id': type_domain,
        }
        return {'domain': domain}

    @api.one
    @api.depends('left_partner_id', 'right_partner_id')
    def _compute_any_partner_id(self):
        self.any_partner_id = self.left_partner_id + self.right_partner_id

    @api.model
    def _search_any_partner_id(self, operator, value):
        return [
            '|',
            ('left_partner_id', operator, value),
            ('right_partner_id', operator, value),
        ]

    @api.multi
    def _on_right_partner(self):
        """Determine wether functions are called in a situation where the
        active partner is the right partner. Default False!
        """
        return set(self.mapped('right_partner_id').ids) &\
            set(self.env.context.get('active_ids', []))

    @api.model
    def get_type_from_selection_id(self, selection_type_id):
        """Return tuple with type_id and reverse indication for
        selection_type_id."""
        selection_model = self.env['res.partner.relation.type.selection']
        selection = selection_model.browse(selection_type_id)
        return selection.get_type_from_selection_id()

    @api.model
    def _correct_vals(self, vals):
        """Fill type and left and right partner id, according to whether
        we have a normal relation type or an inverse relation type
        """
        vals = vals.copy()
        if 'type_selection_id' not in vals:
            return vals
        type_id, is_reverse = self.get_type_from_selection_id(
            vals['type_selection_id']
        )
        vals['type_id'] = type_id
        # If adding through view with just left_partner_id
        # and right_partner_id, we have to use those, and not look at
        # other fields:
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
        return vals

    @api.multi
    def write(self, vals):
        """Override write to correct values, before being stored."""
        vals = self._correct_vals(vals)
        return super(ResPartnerRelation, self).write(vals)

    @api.model
    def create(self, vals):
        """Override create to correct values, before being stored."""
        context = self.env.context
        if 'left_partner_id' not in vals and context.get('active_id'):
            vals['left_partner_id'] = context.get('active_id')
        vals = self._correct_vals(vals)
        return super(ResPartnerRelation, self).create(vals)

    @api.one
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """End date should not be before start date, if not filled

        :raises exceptions.Warning: When constraint is violated
        """
        if (self.date_start and self.date_end and
                self.date_start > self.date_end):
            raise exceptions.Warning(
                _('The starting date cannot be after the ending date.')
            )

    @api.one
    @api.constrains('left_partner_id', 'type_id')
    def _check_partner_type_left(self):
        """Check left partner for required company or person

        :raises exceptions.Warning: When constraint is violated
        """
        self._check_partner_type("left")

    @api.one
    @api.constrains('right_partner_id', 'type_id')
    def _check_partner_type_right(self):
        """Check right partner for required company or person

        :raises exceptions.Warning: When constraint is violated
        """
        self._check_partner_type("right")

    @api.one
    def _check_partner_type(self, side):
        """Check partner to left or right for required company or person

        :param str side: left or right
        :raises exceptions.Warning: When constraint is violated
        """
        assert side in ['left', 'right']
        ptype = getattr(self.type_id, "contact_type_%s" % side)
        company = getattr(self, '%s_partner_id' % side).is_company
        if (ptype == 'c' and not company) or (ptype == 'p' and company):
            raise exceptions.Warning(
                _('The %s partner is not applicable for this relation type.') %
                side
            )

    @api.one
    @api.constrains('left_partner_id', 'right_partner_id')
    def _check_not_with_self(self):
        """Not allowed to link partner to same partner

        :raises exceptions.Warning: When constraint is violated
        """
        if self.left_partner_id == self.right_partner_id:
            if not self.allow_self:
                raise exceptions.Warning(
                    _('Partners cannot have a relation with themselves.')
                )

    @api.one
    @api.constrains('left_partner_id', 'right_partner_id', 'active')
    def _check_relation_uniqueness(self):
        """Forbid multiple active relations of the same type between the same
        partners

        :raises exceptions.Warning: When constraint is violated
        """
        if not self.active:
            return
        domain = [
            ('type_id', '=', self.type_id.id),
            ('active', '=', True),
            ('id', '!=', self.id),
            ('left_partner_id', '=', self.left_partner_id.id),
            ('right_partner_id', '=', self.right_partner_id.id),
        ]
        if self.date_start:
            domain += [
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', self.date_start),
            ]
        if self.date_end:
            domain += [
                '|',
                ('date_start', '=', False),
                ('date_start', '<=', self.date_end),
            ]
        if self.search(domain):
            raise exceptions.Warning(
                _('There is already a similar relation with overlapping dates')
            )
