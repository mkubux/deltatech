# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import odoo
from odoo import models, fields, api, tools, _
from odoo.exceptions import except_orm, Warning, RedirectWarning
import odoo.addons.decimal_precision as dp

from odoo.tools import html2plaintext


class crm_case_categ(models.Model):
    """ Category of Case """
    _name = "crm.case.categ"
    _description = "Category of Case"


    name = fields.Char('Name', required=True, translate=True)
    section_id = fields.Many2one('crm.team', 'Sales Team')
    object_id = fields.Many2one('ir.model', 'Object Name')




    def _find_object_id(self, cr, uid, context=None):
        """Finds id for case object"""
        context = context or {}
        object_id = context.get('object_id', False)
        ids = self.pool.get('ir.model').search(cr, uid, ['|', ('id', '=', object_id), ('model', '=', context.get('object_name', False))])
        return ids and ids[0] or False
    _defaults = {
        'object_id': _find_object_id
    }



class crm_claim_stage(models.Model):

    """ Model for claim stages. This models the main stages of a claim
        management flow. Main CRM objects (leads, opportunities, project
        issues, ...) will now use only stages, instead of state and stages.
        Stages are for example used to display the kanban view of records.
    """
    _name = "crm.claim.stage"
    _description = "Claim stages"
    _rec_name = 'name'
    _order = "sequence"



    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', help="Used to order stages. Lower is better.", default=1)
    section_ids = fields.Many2many('crm.team', 'section_claim_stage_rel', 'stage_id', 'section_id', string='Sections',
                    help="Link between stages and sales teams. When set, this limitate the current stage to the selected sales teams.")
    case_default = fields.Boolean('Common to All Teams',
                    help="If you check this field, this stage will be proposed by default on each sales team. It will not assign this stage to existing teams.")



class crm_claim(models.Model):

    """ Crm claim
    """
    _name = "crm.claim"
    _description = "Claim"
    _order = "priority,date desc"
    _inherit = ['mail.thread']


    def _resolve_section_id_from_context(self, cr, uid, context=None):
        """ Returns ID of section based on the value of 'section_id'
            context key, or None if it cannot be resolved to a single
            Sales Team.
        """
        if context is None:
            context = {}
        if type(context.get('default_section_id')) in (int, long):
            return context.get('default_section_id')
        if isinstance(context.get('default_section_id'), basestring):

            section_ids = self.pool.get('crm.team').name_search(cr, uid, name=context['default_section_id'], context=context)

            if len(section_ids) == 1:
                return int(section_ids[0][0])
        return None


   
    def _get_default_section_id(self, cr, uid, context=None):

        return self._resolve_section_id_from_context(cr, uid, context=context) or False
  
    
    def _get_default_stage_id(self, cr, uid, context=None):

        section_id = self._get_default_section_id(cr, uid, context=context)
        return self.stage_find(cr, uid, [], section_id, [('sequence', '=', '1')], context=context)
  
    


    id = fields.Integer('ID', readonly=True)
    name = fields.Char('Claim Subject', required=True)
    active = fields.Boolean('Active')
    action_next = fields.Char('Next Action')
    date_action_next = fields.Datetime('Next Action Date')
    description = fields.Text('Description')
    resolution = fields.Text('Resolution')
    create_date = fields.Datetime('Creation Date' , readonly=True)
    write_date = fields.Datetime('Update Date' , readonly=True)
    date_deadline = fields.Date('Deadline')
    date_closed = fields.Datetime('Closed', readonly=True)
    date = fields.Datetime('Claim Date', select=True)
    ref = fields.Reference(odoo.addons.base.res.res_request.referenceable_models, string='Reference')
    categ_id = fields.Many2one('crm.case.categ', 'Category', \
                        domain="[('section_id','=',section_id),\
                        ('object_id.model', '=', 'crm.claim')]")
    priority = fields.Selection([('0','Low'), ('1','Normal'), ('2','High')], 'Priority')
    type_action = fields.Selection([('correction','Corrective Action'),('prevention','Preventive Action')], 'Action Type')
    user_id = fields.Many2one('res.users', 'Responsible', track_visibility='always')
    user_fault = fields.Char('Trouble Responsible')
    section_id = fields.Many2one('crm.team', 'Sales Team', \
                    select=True, help="Responsible sales team."\
                            " Define Responsible user and Email account for"\
                            " mail gateway.")
    company_id = fields.Many2one('res.company', 'Company')
    partner_id = fields.Many2one('res.partner', 'Partner')
    email_cc = fields.Text('Watchers Emails', size=252, help="These email addresses will be added to the CC field of all inbound and outbound emails for this record before being sent. Separate multiple email addresses with a comma"),
    email_from = fields.Char('Email', size=128, help="Destination email for email gateway.")
    partner_phone = fields.Char('Phone')
    stage_id = fields.Many2one ('crm.claim.stage', string='Stage', track_visibility='onchange',
            domain="['|', ('section_ids', '=', section_id), ('case_default', '=', True)]")
    cause = fields.Text('Root Cause')



    _defaults = {
        'user_id': lambda s, cr, uid, c: uid,
        'section_id': lambda s, cr, uid, c: s._get_default_section_id(cr, uid, c),
        'date': fields.datetime.now,
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'crm.case', context=c),
        'priority': '1',
        'active': lambda *a: 1,
        'stage_id': lambda s, cr, uid, c: s._get_default_stage_id(cr, uid, c)
    }

    def stage_find(self, cr, uid, cases, section_id, domain=[], order='sequence', context=None):
        """ Override of the base.stage method
            Parameter of the stage search taken from the lead:
            - section_id: if set, stages must belong to this section or
              be a default case
        """
        if isinstance(cases, (int, long)):
            cases = self.browse(cr, uid, cases, context=context)
        # collect all section_ids
        section_ids = []
        if section_id:
            section_ids.append(section_id)
        for claim in cases:
            if claim.section_id:
                section_ids.append(claim.section_id.id)
        # OR all section_ids and OR with case_default
        search_domain = []
        if section_ids:
            search_domain += [('|')] * len(section_ids)
            for section_id in section_ids:
                search_domain.append(('section_ids', '=', section_id))
        search_domain.append(('case_default', '=', True))
        # AND with the domain in parameter
        search_domain += list(domain)
        # perform search, return the first found
        stage_ids = self.pool.get('crm.claim.stage').search(cr, uid, search_domain, order=order, context=context)
        if stage_ids:
            return stage_ids[0]
        return False



    @api.multi
    def onchange_partner_id(self,   partner_id, email=False ):

        """This function returns value of partner address based on partner
           :param email: ignored
        """
        if not partner_id:
            return {'value': {'email_from': False, 'partner_phone': False}}

        address = self.env['res.partner'].browse(  partner_id )

        return {'value': {'email_from': address.email, 'partner_phone': address.phone}}

    def create(self, cr, uid, vals, context=None):
        context = dict(context or {})
        if vals.get('section_id') and not context.get('default_section_id'):
            context['default_section_id'] = vals.get('section_id')

        # context: no_log, because subtype already handle this
        return super(crm_claim, self).create(cr, uid, vals, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        claim = self.browse(cr, uid, id, context=context)
        default = dict(default or {},
            stage_id = self._get_default_stage_id(cr, uid, context=context),
            name = _('%s (copy)') % claim.name)
        return super(crm_claim, self).copy(cr, uid, id, default, context=context)

    # -------------------------------------------------------
    # Mail gateway
    # -------------------------------------------------------

    def message_new(self, cr, uid, msg, custom_values=None, context=None):
        """ Overrides mail_thread message_new that is called by the mailgateway
            through message_process.
            This override updates the document according to the email.
        """
        if custom_values is None:
            custom_values = {}
        desc = html2plaintext(msg.get('body')) if msg.get('body') else ''
        defaults = {
            'name': msg.get('subject') or _("No Subject"),
            'description': desc,
            'email_from': msg.get('from'),
            'email_cc': msg.get('cc'),
            'partner_id': msg.get('author_id', False),
        }
        if msg.get('priority'):
            defaults['priority'] = msg.get('priority')
        defaults.update(custom_values)
        return super(crm_claim, self).message_new(cr, uid, msg, custom_values=defaults, context=context)



class res_partner(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def _claim_count(self):
        for partner in self:
            partner.claim_count = self.env['crm.claim'].search_count([('partner_id', '=', partner.id)])

    claim_count = fields.Integer(compute="_claim_count", string='# Claims')



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
