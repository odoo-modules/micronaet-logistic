#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import logging
import odoo
import shutil
from odoo import api, fields, models, tools, exceptions, SUPERUSER_ID
from odoo.addons import decimal_precision as dp
from odoo.tools.translate import _

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


_logger = logging.getLogger(__name__)

class CrmTeam(models.Model):
    """ Model name: CRM Team
    """

    _inherit = 'crm.team'

    channel_ref = fields.Char('Channel', size=20)
    team_code_ref = fields.Char('Team code ref.', size=20)
    market_type = fields.Selection((
        ('b2b', 'B2B'),
        ('b2c', 'B2C'),
        ), 'Market type')

class ResCompany(models.Model):
    """ Model name: Res Company
    """

    _inherit = 'res.company'

    # -------------------------------------------------------------------------
    # Parameters:
    # -------------------------------------------------------------------------
    # Database structure:
    _logistic_folder_db = {
            'images': {
                'default': 'images',
                },
            'corrispettivi': {
                'default': 'Corrispettivi',
                }

            # TODO label, picking out?, Invoice, DDT
            }

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def formatLang(self, value, date=True, date_time=False):
        ''' Fake function for format Format date passed
        '''
        # Change italian mode:
        if not value:
            return value
        res = '%s/%s/%s%s' % (
            value[8:10],
            value[5:7],
            value[:4],
            value[10:],
            )
        if date_time:
            return res
        elif date:
            return res[:10]

    # Get path name:
    @api.model
    def _logistic_folder(self, document, mode='default', extra=False):
        ''' Return full path of folder request:
        '''
        # Get master path:
        folder_block = self._logistic_folder_db[document][mode]

        # Manage extra path:
        if extra:
            if type(extra) == str:
                extra = [extra]
            elif type(extra) == tuple:
                extra = list(extra)
            folder_block = list(folder_block).extend(extra)
        return self.get_subfolder_from_root(folder_block)

    @api.model
    def get_subfolder_from_root(self, name):
        ''' Get subfolder from root
            if str only one folder, instead multipath
        '''
        try:
            if type(name) == str:
                name = (name, )
            folder = os.path.expanduser(
                os.path.join(self.logistic_root_folder, *name))

            # Create in not present
            os.system('mkdir -p %s' % folder)
        except:
            raise odoo.exceptions.Warning(
                _('Error creating output folder (check param)'))
        return folder

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    # Pick type for load / unload:
    logistic_pick_in_type_id = fields.Many2one(
        'stock.picking.type', 'Pick in type',
        help='Picking in type for load documents',
        required=True,
        )
    logistic_pick_out_type_id = fields.Many2one(
        'stock.picking.type', 'Pick out type',
        help='Picking in type for unload documents',
        required=True,
        )
    logistic_root_folder = fields.Text(
        'Output root folder',
        help='Master root folder for output',
        required=True,
        )
    product_account_ref = fields.Char('Product account ref.', size=20)


class ProductTemplate(models.Model):
    ''' Template add fields
    '''
    _inherit = 'product.template'

    @api.model
    def _get_root_image_folder(self):
        ''' Use filestrore folder and subfolder images
        '''
        company_pool = self.env['res.company']
        companys = company_pool.search([])
        return companys[0]._logistic_folder('images')

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    is_expence = fields.Boolean('Expense product',
        help='Expense product is not order and produced')
    account_ref = fields.Char('Account ref.', size=20,
        help='Account code, if not present use default setup in configuration')

class PurchaseOrder(models.Model):
    """ Model name: Sale Order
    """

    _inherit = 'purchase.order'

    # -------------------------------------------------------------------------
    #                           UTILITY:
    # -------------------------------------------------------------------------
    # Auto close internal order
    @api.model
    def purchase_internal_confirmed(self, purchases=None):
        ''' Check if there's some PO internal to close
        '''

        # TODO schedule action?
        # Pool used:
        company_pool = self.env['res.company']
        move_pool = self.env['stock.move']
        sale_line_pool = self.env['sale.order.line']
        picking_pool = self.env['stock.picking']

        # Parameter:
        company = company_pool.search([])[0]
        logistic_pick_in_type = company.logistic_pick_in_type_id
        logistic_pick_in_type_id = logistic_pick_in_type.id
        location_from = logistic_pick_in_type.default_location_src_id.id
        location_to = logistic_pick_in_type.default_location_dest_id.id
        logistic_root_folder = os.path.expanduser(company.logistic_root_folder)

        reply_path = os.path.join(
            logistic_root_folder, 'purchase', 'reply')
        history_path = os.path.join(
            logistic_root_folder, 'purchase', 'history')

        sale_line_ready = [] # ready line after assign load qty to purchase
        move_file = []
        for root, subfolders, files in os.walk(reply_path):
            for f in files:
                po_id = int(f[:-4].split('_')[-1]) # pick_in_ID.csv
                # TODO Mark as sync: quants.write({'account_sync': True, })

                # Read picking and create Fake BF for load stock
                purchase = self.browse(po_id)
                if purchase.logistic_state == 'done':
                    _logger.error('Order yet manage: %s (remove manually)' % f)
                    continue

                # -------------------------------------------------------------
                # Create picking:
                # -------------------------------------------------------------
                try:
                    order = purchase.order_line[0].logistic_sale_id.order_id
                except:
                    # Empty order: (cancel before load in account)
                    purchase.logistic_state = 'done'

                    # Save move operation:
                    move_file.append((
                        os.path.join(reply_path, f),
                        os.path.join(history_path, f),
                        ))
                    continue

                partner = order.partner_id
                date = purchase.date_order
                name = purchase.name or ''
                origin = _('%s [%s]') % (name, date)

                picking = picking_pool.create({
                    'partner_id': partner.id,
                    'scheduled_date': date,
                    'origin': origin,
                    #'move_type': 'direct',
                    'picking_type_id': logistic_pick_in_type_id,
                    'group_id': False,
                    'location_id': location_from,
                    'location_dest_id': location_to,
                    #'priority': 1,
                    'state': 'done', # immediately!
                    })

                # -----------------------------------------------------------------
                # Append stock.move detail (or quants if in stock)
                # -----------------------------------------------------------------
                for line in purchase.order_line:
                    product = line.product_id
                    product_qty = line.product_qty
                    remain_qty = line.logistic_undelivered_qty
                    logistic_sale_id = line.logistic_sale_id

                    if product_qty >= remain_qty:
                        sale_line_ready.append(logistic_sale_id)
                        logistic_sale_id.logistic_state = 'ready' # XXX needed?

                    # ---------------------------------------------------------
                    # Create movement (not load stock):
                    # ---------------------------------------------------------
                    move_pool.create({
                        'company_id': company.id,
                        'partner_id': partner.id,
                        'picking_id': picking.id,
                        'product_id': product.id,
                        'name': product.name or ' ',
                        'date': date,
                        'date_expected': date,
                        'location_id': location_from,
                        'location_dest_id': location_to,
                        'product_uom_qty': product_qty,
                        'product_uom': product.uom_id.id,
                        'state': 'done',
                        'origin': origin,

                        # Sale order line link:
                        'logistic_load_id': logistic_sale_id.id,
                        # Purchase order line line:
                        'logistic_purchase_id': line.id,
                        })

                # Save move operation:
                move_file.append((
                    os.path.join(reply_path, f),
                    os.path.join(history_path, f),
                    ))

                # Mask as done fake purchase order:
                purchase.logistic_state = 'done'
                _logger.info('Purchase order: %s done!' % f)

            break # only first folder

        # ---------------------------------------------------------------------
        # Check Sale Order header with all line ready:
        # ---------------------------------------------------------------------
        _logger.info('Update sale order header as ready:')
        sale_line_pool.logistic_check_ready_order(sale_line_ready)

        # ---------------------------------------------------------------------
        # Move all files read:
        # ---------------------------------------------------------------------
        _logger.info('Move all files:')
        for from_file, to_file in move_file:
            # Move when all is done!
            try:
                shutil.move(from_file, to_file)
            except:
                _logger.error('Error moving operation: %s >> %s' % (
                    from_file, to_file))
        return True

    @api.model
    def return_purchase_order_list_view(self, purchase_ids):
        ''' Return purchase order tree from ids
        '''
        model_pool = self.env['ir.model.data']
        tree_view_id = form_view_id = False

        if len(purchase_ids) == 1:
            res_id = purchase_ids[0]
            views = [(form_view_id, 'form'), (tree_view_id, 'tree')]
        else:
            res_id = False
            views = [(tree_view_id, 'tree'), (form_view_id, 'form')]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase order selected:'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_id': res_id,
            'res_model': 'purchase.order',
            'view_id': tree_view_id,
            'views': views,
            'domain': [('id', 'in', purchase_ids)],
            'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    @api.model
    def check_order_confirmed_done(self, purchase_ids=None):
        ''' Check passed purchase IDs passed or all confirmed order
            if not present
        '''
        if purchase_ids:
            purchases = self.browse(purchase_ids)
        else:
            purchases = self.search([('logistic_state', '=', 'confirmed')])

        for purchase in purchases:
            done = True

            for line in purchase.order_line:
                if line.logistic_undelivered_qty > 0:
                    done = False
                    break
            # Update if all line hasn't undelivered qty
            if done:
                purchase.logistic_state = 'done'
        return True

    # -------------------------------------------------------------------------
    #                            BUTTON:
    # -------------------------------------------------------------------------
    @api.multi
    def open_purchase_line(self):
        ''' Open purchase line detail view:
        '''
        model_pool = self.env['ir.model.data']
        tree_view_id = model_pool.get_object_reference(
            'tyres_logistic_management', 'view_purchase_order_line_tree')[1]
        form_view_id = model_pool.get_object_reference(
            'tyres_logistic_management', 'view_purchase_order_line_form')[1]

        line_ids = [item.id for item in self.order_line]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase line'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'purchase.order.line',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': self.env.context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    # Workflow button:
    @api.multi
    def set_logistic_state_confirmed(self):
        ''' Set order as confirmed
        '''
        # Export if needed the purchase order:
        # TODO self.export_purchase_order()
        now = fields.Datetime.now()

        return self.write({
            'logistic_state': 'confirmed',
            'date_planned': now,
            })

    # -------------------------------------------------------------------------
    #                                COLUMNS:
    # -------------------------------------------------------------------------
    logistic_state = fields.Selection([
        ('draft', 'Order draft'), # Draft purchase
        ('confirmed', 'Confirmed'), # Purchase confirmed
        ('done', 'Done'), # All loaded in stock
        ], 'Logistic state', default='draft',
        )

class PurchaseOrderLine(models.Model):
    """ Model name: Purchase Order Line
    """

    _inherit = 'purchase.order.line'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    # RELATIONAL FIELDS:
    logistic_sale_id = fields.Many2one(
        'sale.order.line', 'Link to generator',
        help='Link generator sale order line: one customer line=one purchase',
        index=True, ondelete='set null',
        )

class StockMoveIn(models.Model):
    """ Model name: Stock Move
    """

    _inherit = 'stock.move'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    # Direct link to sale order line (generated from purchase order):
    logistic_refund_id = fields.Many2one(
        'sale.order.line', 'Link refund to sale',
        help='Link pick refund line to original sale line',
        index=True, ondelete='set null',
        )

    # Direct link to sale order line (generated from purchase order):
    logistic_load_id = fields.Many2one(
        'sale.order.line', 'Link load to sale',
        help='Link pick in line to original sale line (bypass purchase)',
        index=True, ondelete='set null',
        )

    # DELIVER: Pick out
    logistic_unload_id = fields.Many2one(
        'sale.order.line', 'Link unload to sale',
        help='Link pick out line to sale order',
        index=True, ondelete='set null',
        )

    # SUPPLIER ORDER: Purchase management:
    logistic_purchase_id = fields.Many2one(
        'purchase.order.line', 'Link load to purchase',
        help='Link pick in line to generat purchase line',
        index=True, ondelete='set null',
        )

    # LOAD WITHOUT SUPPLIER: Load management:
    # XXX Remove:
    logistic_quant_id = fields.Many2one(
        'stock.quant', 'Stock quant',
        help='Link to stock quant generated (load / unoad data).',
        index=True, ondelete='cascade',
        )

class PurchaseOrderLine(models.Model):
    """ Model name: Purchase Order Line
    """

    _inherit = 'purchase.order.line'

    # -------------------------------------------------------------------------
    # Function fields:
    # -------------------------------------------------------------------------
    #@api.depends('load_line_ids', )
    @api.multi
    def _get_logistic_status_field(self):
        ''' Manage all data for logistic situation in sale order:
        '''
        _logger.warning('Update logistic qty fields now')
        for line in self:
            logistic_delivered_qty = 0.0
            for move in line.load_line_ids:
                logistic_delivered_qty += move.product_uom_qty
            # Generate data for fields:
            line.logistic_delivered_qty = logistic_delivered_qty
            line.logistic_undelivered_qty = \
                line.product_qty - logistic_delivered_qty

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    # COMPUTED:
    logistic_delivered_qty = fields.Float(
        'Delivered qty', digits=dp.get_precision('Product Price'),
        help='Qty delivered with load documents',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_undelivered_qty = fields.Float(
        'Undelivered qty', digits=dp.get_precision('Product Price'),
        help='Qty undelivered, remain to load',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )

    # TODO logistic state?
    # RELATIONAL:
    load_line_ids = fields.One2many(
        'stock.move', 'logistic_purchase_id', 'Linked load to purchase',
        help='Load linked to this purchase line',
        )

class StockPicking(models.Model):
    """ Model name: Stock picking
    """

    _inherit = 'stock.picking'

    @api.multi
    def refund_confirm_state_event(self):
        ''' Confirm operation (will be overrided)
        '''
        # Confirm document and export in files:
        self.workflow_ready_to_done_done_picking()
        return True

    # -------------------------------------------------------------------------
    # Extract Excel:
    # -------------------------------------------------------------------------
    @api.model
    def reply_csv_accounting_fees(self):
        '''
        '''
        # TODO
        return True

    @api.model
    def csv_report_extract_accounting_fees(self, evaluation_date):
        ''' Extract file account fees in CSV for accounting
        '''

        # Pool used:
        company_pool = self.env['res.company']
        company = company_pool.search([])[0]
        path = os.path.expanduser(company.logistic_root_folder)
        path = os.path.join(path, 'corrispettivi')

        product_account_ref = company.product_account_ref

        try:
            os.system('mkdir -p %s' % path)
            os.system('mkdir -p %s' % os.path.join(path, 'reply'))
            os.system('mkdir -p %s' % os.path.join(path, 'history'))
        except:
            _logger.error('Cannot create %s' % path)

        # Period current date:
        _logger.warning('Account Fees evalutation: %s' % evaluation_date)

        # Picking not invoiced (DDT and Refund):
        pickings = self.search([
            ('is_fees', '=', True),

            # Period:
            ('scheduled_date', '>=', '%s 00:00:00' % evaluation_date),
            ('scheduled_date', '<=', '%s 23:59:59' % evaluation_date),
            # XXX: This? ('ddt_date', '=', now_dt),
            ])

        channel_row = {}
        for picking in pickings:
            # Readability:
            order = picking.sale_order_id
            partner = order.partner_id
            stock_mode = picking.stock_mode #in: refund, out: DDT

            for move in picking.move_lines:
                qty = move.product_uom_qty
                total = qty * move.logistic_unload_id.price_unit

                # Get channel
                try:
                    channel = move.logistic_unload_id.team_id.channel_ref
                except:
                    channel = ''

                # Get partner code
                try:
                    code_ref = move.logistic_unload_id.team_id.team_code_ref
                except:
                    code_ref = ''

                if channel not in channel_row:
                    channel_row[channel] = []

                if stock_mode == 'out':
                    total = -total
                product = move.product_id
                channel_row[channel].append((
                    # XXX Use scheduled date or ddt_date?
                    channel,
                    product.default_code or '',
                    company_pool.formatLang(picking.scheduled_date, date=True),
                    order.payment_term_id.account_ref or '',
                    product.account_ref or product_account_ref or '',
                    qty,
                    total,
                    'S' if product.is_expence else 'M',
                    code_ref, # Agent code
                    ))

        date = evaluation_date.replace('-', '_')
        for channel in channel_row:
            fees_filename = os.path.join(path, '%s_%s.csv' % (channel, date))
            fees_f = open(fees_filename, 'w')

            fees_f.write(
                'CANALE|SKU|DATA|PAGAMENTO|PRODOTTO|Q|TOTALE|TIPO|AGENTE\r\n')
            for row in channel_row[channel]:
                fees_f.write('%s|%s|%s|%s|%s|%s|%s|%s|%s\r\n' % row)
            fees_f.close()

        return True

    # -------------------------------------------------------------------------
    # Extract Excel:
    # -------------------------------------------------------------------------
    @api.model
    def excel_report_extract_accounting_fees(self, evaluation_date=False):
        ''' Extract file account fees
        '''

        # Pool used:
        excel_pool = self.env['excel.writer']
        company_pool = self.env['res.company']

        companys = company_pool.search([])
        fees_path = companys[0]._logistic_folder('corrispettivi')

        # Period current date:
        if evaluation_date: # use evaluation
            now_dt = datetime.strptime(evaluation_date, '%Y-%m-%d')
        else: # use now
            now_dt = datetime.now()
        _logger.warning('Account Fees evalutation: %s' % now_dt)

        from_date = now_dt.strftime('%Y-%m-01')
        now_dt += relativedelta(months=1)
        to_date = now_dt.strftime('%Y-%m-01')

        # Picking not invoiced (DDT and Refund):
        pickings = self.search([
            # Period:
            ('ddt_date', '>=', from_date),
            ('ddt_date', '<', to_date),

            # Not invoiced (only DDT):
            ('ddt_number', '!=', False),
            #('invoice_number', '=', False),
            ])

        ws_name = 'Registro corrispettivi'
        excel_pool.create_worksheet(ws_name)

        ws_invoice = 'Fatturato'
        excel_pool.create_worksheet(ws_invoice)

        # ---------------------------------------------------------------------
        # Format:
        # ---------------------------------------------------------------------
        excel_pool.set_format()
        f_title = excel_pool.get_format('title')
        f_header = excel_pool.get_format('header')
        f_text_black = excel_pool.get_format('text')
        f_text_red = excel_pool.get_format('text_red')
        f_number_black = excel_pool.get_format('number')
        f_number_red = excel_pool.get_format('number_red')
        #f_green_text = excel_pool.get_format('bg_green')
        #f_yellow_text = excel_pool.get_format('bg_yellow')
        #f_green_number = excel_pool.get_format('bg_green_number')
        #f_yellow_number = excel_pool.get_format('bg_yellow_number')

        # ---------------------------------------------------------------------
        # Setup page: Corrispettivo
        # ---------------------------------------------------------------------
        excel_pool.column_width(ws_name, [
            15, 15, 25, 15, 15, 30, 25,
            10, 10, 10,
            ])

        row = 0
        excel_pool.write_xls_line(ws_name, row, [
             'Corrispettivi del periodo: [%s - %s]' % (from_date, to_date)
             ], default_format=f_title)

        row += 1
        excel_pool.write_xls_line(ws_name, row, [
             'Data', 'Data X', 'Ordine', 'Picking', 'Stato',
             'Cliente', 'Posizione fiscale',
             'Imponibile', 'IVA', 'Totale',
             ], default_format=f_header)

        # ---------------------------------------------------------------------
        # Setup page: Fatturato
        # ---------------------------------------------------------------------
        excel_pool.column_width(ws_invoice, [
            15, 15, 25, 15, 15,
            20, 30, 25,
            10, 10, 10,
            ])

        row_invoice = 0
        excel_pool.write_xls_line(ws_invoice, row_invoice, [
             'Fatture del periodo: [%s - %s]' % (from_date, to_date)
             ], default_format=f_title)

        row_invoice += 1
        excel_pool.write_xls_line(ws_invoice, row_invoice, [
             'Data', 'Data X', 'Ordine', 'Picking', 'Stato',
             'Fattura', 'Cliente', 'Posizione fiscale',
             'Imponibile', 'IVA', 'Totale',
             ], default_format=f_header)

        total = {
            'amount': 0.0,
            'vat': 0.0,
            'total': 0.0,
            }

        total_invoice = {
            'amount': 0.0,
            'vat': 0.0,
            'total': 0.0,
            }
        for picking in pickings:
            # Readability:
            order = picking.sale_order_id
            partner = order.partner_id
            stock_mode = picking.stock_mode #in: refund, out: DDT

            if stock_mode == 'in':
                sign = -1.0
                f_number = f_number_red
                f_text = f_text_red
            else:
                f_number = f_number_black
                f_text = f_text_black
                sign = +1.0

            subtotal = { # common subtotal
                'amount': 0.0,
                'vat': 0.0,
                'total': 0.0,
                }

            if picking.invoice_number:
                row_invoice +=1
                for move in picking.move_lines_for_report():
                    subtotal['amount'] += sign * float(move[9]) # Total without VAT
                    subtotal['vat'] += sign * float(move[6]) # VAT Total
                    subtotal['total'] += sign * float(move[10]) # Total with VAT

                # Update total:
                total_invoice['amount'] += subtotal['amount']
                total_invoice['vat'] += subtotal['vat']
                total_invoice['total'] += subtotal['total']

                excel_pool.write_xls_line(ws_invoice, row_invoice, (
                    picking.ddt_date,
                    order.x_ddt_date,
                    picking.ddt_number if stock_mode == 'in' else order.name,
                    picking.name,
                    '' if stock_mode == 'in' else order.logistic_state,
                    picking.invoice_number,
                    partner.name,
                    partner.property_account_position_id.name,
                    (subtotal['amount'], f_number),
                    (subtotal['vat'], f_number),
                    (subtotal['total'], f_number),
                    ), default_format=f_text)

            else: # No invoice:
                row +=1
                for move in picking.move_lines_for_report():
                    subtotal['amount'] += sign * float(move[9]) # Total without VAT
                    subtotal['vat'] += sign * float(move[6]) # VAT Total
                    subtotal['total'] += sign * float(move[10]) # Total with VAT

                # Update total:
                total['amount'] += subtotal['amount']
                total['vat'] += subtotal['vat']
                total['total'] += subtotal['total']

                excel_pool.write_xls_line(ws_name, row, (
                    picking.ddt_date,
                    order.x_ddt_date,
                    picking.ddt_number if stock_mode == 'in' else order.name,
                    picking.name,
                    '' if stock_mode == 'in' else order.logistic_state,
                    partner.name,
                    partner.property_account_position_id.name, # Fiscal position
                    (subtotal['amount'], f_number),
                    (subtotal['vat'], f_number),
                    (subtotal['total'], f_number),
                    ), default_format=f_text)

        # ---------------------------------------------------------------------
        # Totals:
        # ---------------------------------------------------------------------
        # 1. Corrispettivi:
        row += 1
        excel_pool.write_xls_line(ws_name, row, (
            'Totali:',
            (total['amount'], f_number_black),
            (total['vat'], f_number_black),
            (total['total'], f_number_black),
            ), default_format=f_header, col=6)

        # 2. Invoice:
        row_invoice += 1
        excel_pool.write_xls_line(ws_invoice, row_invoice, (
            'Totali:',
            (total_invoice['amount'], f_number_black),
            (total_invoice['vat'], f_number_black),
            (total_invoice['total'], f_number_black),
            ), default_format=f_header, col=7)

        # ---------------------------------------------------------------------
        # Define filename and save:
        # ---------------------------------------------------------------------
        filename = os.path.join(fees_path, '%s_%s_corrispettivi.xlsx' % (
            from_date[:4], from_date[5:7]))
        excel_pool.save_file_as(filename)
        return True

    # -------------------------------------------------------------------------
    # Override path function:
    # -------------------------------------------------------------------------
    # Path: DDT, Invoice (module: logistic_account_report)
    @api.multi
    def get_default_folder_path(self):
        ''' Override default extract DDT function:
        '''
        companys = self.env['res.company'].search([])
        return companys[0]._logistic_folder('ddt')

    @api.multi
    def get_default_folder_invoice_path(self):
        ''' Override default extract Invoice function:
        '''
        companys = self.env['res.company'].search([])
        return companys[0]._logistic_folder('invoice')

    # Path: XML Invoice
    @api.multi
    def get_default_folder_xml_invoice(self):
        ''' Override default extract XML Invoice
        '''
        companys = self.env['res.company'].search([])
        return companys[0]._logistic_folder('invoice', 'xml')

    # -------------------------------------------------------------------------
    #                                   UTILITY:
    # -------------------------------------------------------------------------
    @api.model
    def qweb_format_float(self, value, decimal=2, length=10):
        ''' Format float value
        '''
        if type(value) != float:
            return value

        format_mask = '%%%s.%sf' % (length, decimal)
        return (format_mask % value).strip()

    # TODO Not used, remove?!?
    @api.model
    def workflow_ready_to_done_all_done_picking(self):
        ''' Confirm draft picking documents
        '''
        pickings = self.search([
            ('state', '=', 'draft'),
            # TODO out document! (),
            ])
        return pickings.workflow_ready_to_done_done_picking()

    @api.multi
    def check_import_reply(self):
        ''' Check import reply for INVOICE
        '''
        # TODO schedule action?
        # Pool used:
        company_pool = self.env['res.company']

        # Parameter:
        company = company_pool.search([])[0]
        logistic_root_folder = os.path.expanduser(company.logistic_root_folder)
        reply_path = os.path.join(
            logistic_root_folder, 'invoice', 'reply')
        history_path = os.path.join(
            logistic_root_folder, 'invoice', 'history')

        move_list = []
        for root, subfolders, files in os.walk(reply_path):
            for f in files:
                f_split = f.split('.')
                if len(f_split) != 4:
                    _logger.error('File not with correct syntax: '
                        'pick_in_ID.00001-CEE.20191231.csv')
                    continue

                # TODO Mark as sync: quants.write({'account_sync': True, })
                pick_id = int(f_split[0].split('_')[-1]) # pick_in_ID.csv

                invoice_number = f_split[1]
                invoice_date = f_split[2]

                # Update invoice information on picking:
                try:
                    self.browse(pick_id).write({
                        'invoice_number': invoice_number,
                        'invoice_date': '%s-%s-%s' % (
                            invoice_date[6:8],
                            invoice_date[4:6],
                            invoice_date[:4],
                            ),
                        })
                except:
                    _logger.error('Error update pick as invoice: %s' % (
                        sys.exc_info(),
                        ))
                    continue

                # Move operation:
                move_list.append((
                    os.path.join(reply_path, f),
                    os.path.join(history_path, f),
                    ))
                _logger.info('Pick ID: %s correct!' % f)
            break # Only first folder

        # ---------------------------------------------------------------------
        # Move files after database operation:
        # ---------------------------------------------------------------------
        for from_file, to_file in move_list:
            shutil.move(from_file, to_file)
        return True

    # -------------------------------------------------------------------------
    #                                   BUTTON:
    # -------------------------------------------------------------------------
    @api.multi
    def workflow_ready_to_done_done_picking(self):
        ''' Confirm draft picking documents
        '''
        def get_address(partner):
            return '%s %s|%s|%s|%s|%s|%s' % (
                partner.street or '',
                partner.street2 or '',

                partner.zip,
                partner.city or '',
                partner.state_id.name or '',
                partner.country_id.name,
                partner.country_id.code,
                )

        # Pool used:
        company_pool = self.env['res.company']

        # Parameter:
        company = company_pool.search([])[0]
        logistic_root_folder = os.path.expanduser(company.logistic_root_folder)

        # ---------------------------------------------------------------------
        # Confirm pickign for DDT and Invoice:
        # ---------------------------------------------------------------------
        invoice_ids = [] # For extra operation after
        for picking in self:
            # Readability:
            order = picking.sale_order_id
            partner = order.partner_invoice_id or order.partner_id
            address = order.partner_shipping_id

            # Need invoice check (fiscal position or order check):
            need_invoice = \
                partner.property_account_position_id.need_invoice or \
                    partner.need_invoice or order.need_invoice
            is_fees = True # default

            # Invoice procedure (check rules):
            if need_invoice:
                is_fees = False

                # -------------------------------------------------------------
                # Extract invoice from account:
                # -------------------------------------------------------------
                path = os.path.join(logistic_root_folder, 'invoice')
                invoice_filename = os.path.join(
                    path, 'pick_in_%s.csv' % picking.id)

                try:
                    os.system('mkdir -p %s' % path)
                    os.system('mkdir -p %s' % os.path.join(path, 'reply'))
                    os.system('mkdir -p %s' % os.path.join(path, 'history'))
                except:
                    _logger.error('Cannot create %s' % path)
                invoice_file = open(invoice_filename, 'w')

                # Export syntax:
                cols = 26
                invoice_file.write(
                    'RAGIONE SOCIALE|'
                    'INDIRIZZO|ZIP|CITTA|PROVINCIA|NAZIONE|ISO CODE|'
                    'PARTITA IVA|CODICE FISCALE|'
                    'EMAIL|TELEFONO|ID CLIENTE|PEC|SDI|NOME DESTINAZIONE|TIPO|'
                    'INDIRIZZO|ZIP|CITTA|PROVINCIA|NAZIONE|ISO CODE|'
                    'ID DESTINAZIONE|DATI BANCARI|ID ORDINE|'
                    'RIF. ORDINE|DATA ORDINE|TIPO DOCUMENTO|COLLI|PESO TOTALE|'
                    'SKU|DESCRIZIONE|QTA|PREZZO|IVA|AGENTE MAGO\r\n'
                    )

                mask = '%s|' * (cols - 1) + '%s\r\n' # 25 fields

                # Parse extra data:
                if order.carrier_shippy:
                    weight = sum([item.weight for item in order.parcel_ids])
                    parcel = len(order.parcel_ids)
                else:
                    weight = order.carrier_manual_weight
                    parcel = order.carrier_manual_parcel

                for move in self.move_lines:
                    line = move.logistic_unload_id
                    invoice_file.write(mask % (
                        partner.name,
                        get_address(partner),
                        partner.vat or '',
                        partner.fatturapa_fiscalcode or '',

                        partner.email or '',
                        partner.phone or '',
                        partner.id,
                        partner.fatturapa_pec or '',
                        partner.fatturapa_unique_code or '',
                        address.name,

                        'privato' if partner.fatturapa_surname else 'business',
                        get_address(address),
                        address.id,
                        '', # TODO Account ID of Bank
                        order.id,

                        order.name or '',
                        company_pool.formatLang(
                            order.date_order, date=True),
                        partner.property_account_position_id.id, # ODOO ID
                        parcel,
                        weight,

                        move.product_id.default_code or '',
                        move.name or '',
                        move.product_uom_qty,
                        line.price_unit, # XXX read from line
                        line.tax_id[0].account_ref or '', # TODO VAT code, >> sale order line?
                        line.order_id.team_id.channel_ref, # Channel agent code
                        ))
                invoice_file.close()
                self.check_import_reply() # Check previous import reply
                invoice_ids.append(picking.id)

            picking.write({
                'state': 'done', # TODO needed?
                'is_fees': is_fees,
                })

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    sale_order_id = fields.Many2one(
        'sale.order', 'Sale order', help='Sale order generator')
    is_fees = fields.Boolean('Is fees', help='Picking not invoiced for sale')

class ResPartner(models.Model):
    """ Model name: Res Partner
    """

    _inherit = 'res.partner'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    internal_stock = fields.Boolean('Internal Stock',
        help='All order to this supplier is considered as internal')
    need_invoice = fields.Boolean('Always invoice')
    sql_customer_code = fields.Char('SQL customer code', size=20)
    sql_supplier_code = fields.Char('SQL supplier code', size=20)

class AccountFiscalPosition(models.Model):
    """ Model name: Account Fiscal Position
    """

    _inherit = 'account.fiscal.position'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    need_invoice = fields.Boolean('Always invoice')

class AccountPaymentTerm(models.Model):
    """ Model name: Account Payment term
    """

    _inherit = 'account.payment.term'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    account_ref = fields.Char('Account ref.', size=20)

class AccountTax(models.Model):
    """ Model name: Account Payment term
    """

    _inherit = 'account.tax'

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    account_ref = fields.Char('Account ref.', size=20)

class SaleOrder(models.Model):
    """ Model name: Sale Order
    """

    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    #                           SERVER ACTION:
    # -------------------------------------------------------------------------
    @api.model
    def order_ready_excel_report(self):
        ''' Generate ready report
        '''
        # Pool used:
        excel_pool = self.env['excel.writer']
        line_pool = self.env['sale.order.line']

        now = fields.Datetime.now()

        _logger.warning('Ready delivery ref.: %s' % now)

        # Line to delivery:
        lines = line_pool.search([
            ('order_id.logistic_state', '=', 'done'),
            # No service
            ])

        ws_name = _('Consegne pronte')
        excel_pool.create_worksheet(ws_name)

        # ---------------------------------------------------------------------
        # Format:
        # ---------------------------------------------------------------------
        excel_pool.set_format()
        format_type = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'text': {
                'black': excel_pool.get_format('text'),
                'red': excel_pool.get_format('text_red'),
                },
            'number': {
                'black': excel_pool.get_format('number'),
                'red': excel_pool.get_format('number_red'),
                },
            }

        # ---------------------------------------------------------------------
        # Setup page: Corrispettivo
        # ---------------------------------------------------------------------
        excel_pool.column_width(ws_name, [
            15, 50,
            25, 8, 5,
            ])

        row = 0
        excel_pool.write_xls_line(ws_name, row, [
             'Consegne pronte in data: %s' % now
             ], default_format=format_type['title'])

        row += 1
        excel_pool.write_xls_line(ws_name, row, [
             'Articolo',
             'Descrizione',

             'Ordine',
             'Data',
             'Q.',
             ], default_format=format_type['header'])

        for line in sorted(lines, key=lambda x: (
                x.order_id.date_order, x.order_id.name)):
            # Readability:
            order = line.order_id
            partner = order.partner_id
            product = line.product_id

            # Jump expence:
            if product.type == 'service' or product.is_expence:
                continue

            row += 1
            excel_pool.write_xls_line(ws_name, row, (
                product.default_code,
                product.description_sale or \
                    product.titolocompleto or product.name or 'Non trovato',

                order.name,
                order.date_order[:10],
                line.product_uom_qty,
                #(line.product_uom_qty, format_type['number']['black']),
                #logistic_undelivered_qty
                ), default_format=format_type['text']['black'])

        # ---------------------------------------------------------------------
        # Return file:
        # ---------------------------------------------------------------------
        return excel_pool.return_attachment('Consegne del %s' % now)

    @api.model
    def write_log_chatter_message(self, message):
        ''' Write message for log operation in order chatter
        '''
        user = self.env['res.users'].browse(self.env.uid)
        body = _('%s [User: %s]') % (
            message,
            user.name,
            )
        self.message_post(
            body=body,
            #subtype='mt_comment',
            #partner_ids=followers
            )

    # -------------------------------------------------------------------------
    #                           OVERRIDE EVENTS:
    # -------------------------------------------------------------------------
    @api.multi
    def payment_is_done(self):
        """ Update payment field done
        """
        self.payment_done = True

        # ---------------------------------------------------------------------
        # Undo extra setup:
        # ---------------------------------------------------------------------
        for line in self.order_line:
            line.undo_returned = False

        # Lauch draft to order
        res = self.workflow_draft_to_order()

        self.write_log_chatter_message(_('Order marked as payed'))
        return True # not returned the view!

    # -------------------------------------------------------------------------
    #                           BUTTON EVENTS:
    # -------------------------------------------------------------------------
    @api.multi
    def locked_delivery_on(self):
        '''Update fields
        '''
        self.locked_delivery = True

    @api.multi
    def locked_delivery_off(self):
        '''Update fields
        '''
        self.locked_delivery = False

    @api.multi
    def dummy(self):
        '''Do nothing'''
        return True

    # Extra operation before WF
    @api.multi
    def return_order_line_list_view(self):
        ''' Return order line in a tree view
        '''
        line_ids = self[0].order_line.mapped('id')
        return self.env['sale.order.line'].return_order_line_list_view(
            line_ids)

    @api.multi
    def workflow_manual_order_pending(self):
        ''' If order have all line checked make one step in pending state
        '''
        # ---------------------------------------------------------------------
        #                             Go in pending
        # ---------------------------------------------------------------------
        if self.logistic_state != 'order':
            raise exceptions.UserError(
                _('Only order in confirmed payment could go in pending!'))

        for line in self.order_line:
            if line.logistic_state != 'ready' and not line.state_check:
                raise exceptions.UserError(
                _('Not all line are mapped to supplier!'))

        # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        # XXX DISABLE INSTRUCTION
        #self.logistic_state = 'ready'
        # XXX ENABLE INSTRUCTION
        self.logistic_state = 'pending'
        # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

        # ---------------------------------------------------------------------
        #                            Generate purchase:
        # ---------------------------------------------------------------------
        # Filter only draft line for this order:
        line_pool = self.env['sale.order.line']

        lines = line_pool.search([
            ('order_id', '=', self.id),
            ('logistic_state', '=', 'draft'),
            ])

        # In undo operation could be returned so check also:
        lines_not_draft = line_pool.search([
            ('order_id', '=', self.id),
            ('logistic_state', '!=', 'draft'),
            ])

        if not lines and not lines_not_draft:
            raise exceptions.UserError(_('No order line to order!'))

        # Call original action:
        line_pool.workflow_order_pending(lines)
        return True # Return nothing

    # -------------------------------------------------------------------------
    #                           UTILITY:
    # -------------------------------------------------------------------------
    @api.multi # XXX not api.one?!?
    def logistic_check_and_set_ready(self):
        ''' Check if all line are in ready state (excluding unused)
        '''
        order_ids = []
        for order in self:
            line_state = set(order.order_line.mapped('logistic_state'))
            line_state.discard('unused') # remove kit line (exploded)
            line_state.discard('done') # if some line are in done multidelivery
            if tuple(line_state) == ('ready', ): # All ready
                if order.logistic_source in ('internal', 'workshop', 'resell'):
                    order.logistic_state = 'done'
                else:
                    order.logistic_state = 'ready'
                order_ids.append(order.id)

        _logger.warning('Closed because ready # %s order' % len(order_ids))
        return order_ids

    @api.multi
    def logistic_check_and_set_done(self):
        ''' Check if all line are in done state (excluding unused)
        '''
        order = self
        line_state = set(order.order_line.mapped('logistic_state'))
        line_state.discard('unused') # remove kit line (exploded)
        if tuple(line_state) == ('done', ): # All done
            order.write({
                'logistic_state': 'done',
                })
        return True

    # Extra operation before WF
    @api.model
    def return_order_list_view(self, order_ids):
        ''' Utility for return selected order in tree view
        '''
        tree_view_id = form_view_id = False
        _logger.info('Return order tree view [# %s]' % len(order_ids))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Order confirmed'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'sale.order',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', order_ids)],
            'context': self.env.context,
            'target': 'current',
            'nodestroy': False,
            }

    def check_empty_orders(self):
        ''' Mark empty order as unused
        '''
        orders = self.search([
            ('logistic_state', '=', 'draft'), # Insert order
            ('order_line', '=', False), # Without line
            ])
        _logger.info('New order: Empty order [# %s]' % len(orders))

        return orders.write({
            'logistic_state': 'error',
            })

    def check_product_service(self):
        ''' Update line with service to ready state
        '''
        line_pool = self.env['sale.order.line']
        lines = line_pool.search([
            ('order_id.logistic_state', '=', 'draft'), # Draft order
            ('logistic_state', '=', 'draft'), # Draft line
             # Direct ready:
            ('product_id.type', '=', 'service'),
            ('product_id.is_expence', '=', True),
            ])
        _logger.info('New order: Check product-service [# %s]' % len(lines))
        return lines.write({
            'logistic_state': 'ready', # immediately ready
            })

    # -------------------------------------------------------------------------
    #                   WORKFLOW: [LOGISTIC OPERATION TRIGGER]
    # -------------------------------------------------------------------------
    # 0. Cancel error order
    # -------------------------------------------------------------------------
    @api.multi
    def wk_order_cancel(self):
        ''' Cancel order (only error state)
        '''
        self.logistic_state = 'cancel'

    # A. Logistic phase 1: Check secure payment:
    # -------------------------------------------------------------------------
    @api.model
    def workflow_draft_to_order(self):
        ''' Assign logistic_state to secure order
        '''
        _logger.info('New order: Start analysis')
        # ---------------------------------------------------------------------
        #                               Pre operations:
        # ---------------------------------------------------------------------
        # Empty orders:
        _logger.info('Check: Mark error state for empty orders')
        self.check_empty_orders() # Order without line

        # Payment article (not kit now):
        _logger.info('Check: Mark service line to ready (not lavoration)')
        self.check_product_service() # Line with service article (not used)

        # ---------------------------------------------------------------------
        # Start order payment check:
        # ---------------------------------------------------------------------
        orders = self.search([
            ('logistic_state', '=', 'draft'), # new order
            ])
        _logger.info('New order: Selection [# %s]' % len(orders))

        # Search new order:
        payment_order = []
        for order in orders:
            # -----------------------------------------------------------------
            # 1. Marked as done (script or in form)
            # -----------------------------------------------------------------
            if order.payment_done:
                payment_order.append(order)
                continue

            # -----------------------------------------------------------------
            # 2. Secure market (sale team):
            # -----------------------------------------------------------------
            try: # error if not present
                if order.team_id.secure_payment:
                    payment_order.append(order)
                    continue
            except:
                pass

            # -----------------------------------------------------------------
            # 3. Secure payment in fiscal position
            # -----------------------------------------------------------------
            try: # problem in not present
                position = order.partner_id.property_account_position_id
                payment = order.payment_term_id
                if payment and payment in [
                        secure.payment_id for secure in position.secure_ids]:
                    payment_order.append(order)
                    continue
            except:
                pass

        # ---------------------------------------------------------------------
        # Update state: order >> payment
        # ---------------------------------------------------------------------
        select_ids = []
        for order in payment_order:
            select_ids.append(order.id)
            order.payment_done = True
            order.logistic_state = 'order'

        # Return view tree:
        return self.return_order_list_view(select_ids)

    # -------------------------------------------------------------------------
    # B. Logistic delivery phase: ready > done
    # -------------------------------------------------------------------------
    # Button call for trigger:
    @api.multi
    def workflow_ready_to_done_current_order(self):
        ''' Button action for call all ready to done order:
        '''
        return self.workflow_ready_to_done_draft_picking()

    # Real trigger call:
    @api.model
    def workflow_ready_to_done_draft_picking(self, ):
        ''' Confirm payment order (before expand kit)
            NOTE: limit, current no more used!
        '''
        self.ensure_one()

        # ---------------------------------------------------------------------
        # TODO Get label PDF for printing
        # ---------------------------------------------------------------------

        # ---------------------------------------------------------------------
        # TODO Print label
        # ---------------------------------------------------------------------

        # ---------------------------------------------------------------------
        # Update Workflow:
        # ---------------------------------------------------------------------
        self.logistic_state = 'delivering'

    # -------------------------------------------------------------------------
    # C. delivering > done
    # -------------------------------------------------------------------------
    @api.multi
    def wf_set_order_as_done(self):
        ''' Set order as done (from delivering)
        '''
        now = fields.Datetime.now()

        # Pool used:
        picking_pool = self.env['stock.picking']
        move_pool = self.env['stock.move']
        company_pool = self.env['res.company']

        # ---------------------------------------------------------------------
        # Parameters:
        # ---------------------------------------------------------------------
        company = company_pool.search([])[0]
        logistic_pick_out_type = company.logistic_pick_out_type_id

        logistic_pick_out_type_id = logistic_pick_out_type.id
        location_from = logistic_pick_out_type.default_location_src_id.id
        location_to = logistic_pick_out_type.default_location_dest_id.id

        # ---------------------------------------------------------------------
        # Select order to prepare:
        # ---------------------------------------------------------------------
        picking_ids = [] # return value
        order = self # readability
        _logger.warning('Generate pick out from order')

        # -----------------------------------------------------------------
        # Create picking out document header:
        # -----------------------------------------------------------------
        partner = order.partner_id
        name = order.name # same as order_ref
        origin = _('%s [%s]') % (order.name, order.create_date[:10])
        picking = picking_pool.create({
            'sale_order_id': order.id, # Link to order
            'partner_id': partner.id,
            'scheduled_date': now,
            'origin': origin,
            #'move_type': 'direct',
            'picking_type_id': logistic_pick_out_type_id,
            'group_id': False,
            'location_id': location_from,
            'location_dest_id': location_to,
            #'priority': 1,
            'state': 'draft', # XXX To do manage done phase (for invoice)!!
            })
        picking_ids.append(picking.id)

        for line in order.order_line:
            product = line.product_id

            # =================================================================
            # Speed up (check if yet delivered):
            # -----------------------------------------------------------------
            # TODO check if there's another cases: service, kit, etc.
            if line.delivered_line_ids:
                product_qty = line.logistic_undelivered_qty
            else:
                product_qty = line.product_uom_qty

            # Update line status:
            line.write({'logistic_state': 'done', })
            # =================================================================

            # -----------------------------------------------------------------
            # Create movement (not load stock):
            # -----------------------------------------------------------------
            # TODO Check kit!!
            move_pool.create({
                'company_id': company.id,
                'partner_id': partner.id,
                'picking_id': picking.id,
                'product_id': product.id,
                'name': product.name or ' ',
                'date': now,
                'date_expected': now,
                'location_id': location_from,
                'location_dest_id': location_to,
                'product_uom_qty': product_qty,
                'product_uom': product.uom_id.id,
                'state': 'done',
                'origin': origin,
                'price_unit': product.standard_price,

                # Sale order line link:
                'logistic_unload_id': line.id,

                # group_id
                # reference'
                # sale_line_id
                # procure_method,
                #'product_qty': select_qty,
                })
        # TODO check if DDT / INVOICE document:

        # ---------------------------------------------------------------------
        # Confirm picking (DDT and INVOICE)
        # ---------------------------------------------------------------------
        # Do all export procedure here:
        picking_pool.browse(picking_ids).workflow_ready_to_done_done_picking()

        # ---------------------------------------------------------------------
        # Order status:
        # ---------------------------------------------------------------------
        # Change status order delivering > done
        order.logistic_check_and_set_done()
        return picking_ids

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    # TODO Raise error:
    @api.onchange('partner_id', 'partner_id.need_invoice')
    def onchange_partner_need_invoice(self):
        ''' Update order status for invoice if change partner or need_invoice
        '''
        self.need_invoice = self.partner_id.need_invoice

    # -------------------------------------------------------------------------
    # Function field:
    # -------------------------------------------------------------------------
    @api.depends('team_id', 'team_id.market_type')
    @api.multi # XXX necessary?
    def _get_market_type(self):
        ''' Update when change the team market
        '''
        for order in self:
            order.market_type = order.team_id.market_type

    # =========================================================================
    #                               UNDO SECTION:
    # =========================================================================
    @api.multi
    def undo_go_in_draft(self):
        ''' Return to draft
        '''
        self.ensure_one()
        if self.logistic_state not in (
                'order', 'ready', 'pending', 'delivering'):
            raise exceptions.UserError(
                _('Only order in confirmed, pending, ready, delivering'
                  ' can undo!'))

        # ---------------------------------------------------------------------
        # Set line for unlinked state:
        # ---------------------------------------------------------------------
        for line in self.order_line:
            if line.delivered_line_ids:
                raise exceptions.UserError(
                    _('Cannot UNDO partial delivery present!'))

            # TODO load stock with received stock
            if line.purchase_line_ids or line.load_line_ids:
                line.undo_returned = True

        # Log operation:
        self.write_log_chatter_message(
            _('Order moved in draft from: %s state') % (
                self.logistic_state,
                ))

        return self.write({
            'logistic_state': 'draft',
            'payment_done': False # Remove OK for payment
            })

    # -------------------------------------------------------------------------
    # Function field:
    # -------------------------------------------------------------------------
    @api.multi
    def _get_undo_comment(self, ):
        ''' Generate undo comment for user
        '''
        self.ensure_one()
        if self.logistic_state == 'draft':
            self.undo_comment = _(
                'Order in <b>draft</b> mode: Do all the change nothing is '
                'needed')
            return
        elif self.logistic_state == 'order':
            self.undo_comment = _(
                'Order <b>confirmed</b>: Need to return in draft mode for '
                'changing if there\'s some difference in payment need also '
                'extra manual operation for correct for ex. paypal amount '
                'received (payment will be confirmed after finish).'
                )
            return
        elif self.logistic_state == 'done':
            self.undo_comment = _(
                'Order <b>done</b> state: No more modify, correct in account '
                'program!'
                )
            return
        elif self.logistic_state == 'cancel':
            self.undo_comment = _(
                'Order <b>cancel</b> state: '
                )
            return
        elif self.logistic_state == 'error':
            self.undo_comment = _(
                'Order <b>error</b> state: '
                )
            return
        # Check what is done:
        # self.logistic_state in ('pending', 'ready'):
        if self.logistic_state == 'pending':
            comment = 'Order in <b>pending</b> status:<br/>'
        elif self.logistic_state == 'ready':
            comment = 'Order in <b>ready</b> status:<br/>'
        elif self.logistic_state == 'delivering':
            comment = 'Order in <b>delivering</b> status:<br/>'

        comment_part = {'purchase': '', 'bf': '', 'bc': ''}
        for sol in self.order_line:
            product = sol.product_id

            # -----------------------------------------------------------------
            # Purchase line present:
            # -----------------------------------------------------------------
            for line in sol.purchase_line_ids:
                partner = line.order_id.partner_id
                if partner.internal_stock:
                    note = _('<b>Need to be uloaded in internal stock!</b>')
                else:
                    note = _('<b>Call %s to remove order!</b>') % partner.name
                if not comment_part['purchase']:
                    comment_part['purchase'] += _(
                        '<br><b>Purchase:</b><br/>'
                        'Need to remove some purchase order line!<br/>'
                        )

                comment_part['purchase'] += _('%s x [%s] %s<br/>') % (
                    line.product_qty,
                    product.default_code or '',
                    note,
                    )

            # -----------------------------------------------------------------
            # BF line present:
            # -----------------------------------------------------------------
            for line in sol.load_line_ids:
                if not comment_part['bf']:
                    comment_part['bf'] += _(
                        '<br><b>Pick in (from supplier):</b><br/>'
                        'Need to move some received product to internal stock'
                        ' stock!<br/>'
                        )
                comment_part['bf'] += _(
                    '%s x [%s]<b> Go to internal stock</b><br/>') % (
                        line.product_uom_qty,
                        product.default_code or '',
                        )

            # -----------------------------------------------------------------
            # Partial of full BC delivery:
            # -----------------------------------------------------------------
            for line in sol.delivered_line_ids:
                if not comment_part['bc']:
                    comment_part['bc'] += _(
                        '<br><b>Pick out (to customer):</b><br/>'
                        '<b><font color="red">'
                        'Delivered to customer line present, nothing to do!'
                        '</font></b><br/>'
                        )
                comment_part['bc'] += _('%s x [%s]<br/>') % (
                    line.product_uom_qty,
                    product.default_code or '',
                    )
        self.undo_comment = comment + ''.join(comment_part.values())

    # -------------------------------------------------------------------------
    # Columns:
    # -------------------------------------------------------------------------
    undo_comment = fields.Text('Undo comment', compute=_get_undo_comment)

    market_type = fields.Selection((
        ('b2b', 'B2B'),
        ('b2c', 'B2C'),
        ), 'Market type', compute='_get_market_type', store=True)

    counter = fields.Integer('Counter', default=1, help='Use for graph view')
    locked_delivery = fields.Boolean('Locked delivery')
    partner_need_invoice = fields.Boolean(
         'Partner need invoice', related='partner_id.need_invoice',
         )
    need_invoice = fields.Boolean(
        'Order need invoice invoice',
        default=lambda s: s.partner_id.need_invoice)

    logistic_picking_ids = fields.One2many(
        'stock.picking', 'sale_order_id', 'Picking')

    logistic_source = fields.Selection([
        ('web', 'Web order'),
        ('resell', 'Customer resell order'),
        ('workshop', 'Workshop order'),
        ('internal', 'Internal provisioning order'),
        ], 'Logistic source', default='web',
        )

    logistic_state = fields.Selection([
        ('draft', 'Order draft'), # Draft, new order received

        # Start automation:
        ('order', 'Order confirmed'), # Quotation transformed in order
        ('pending', 'Pending delivery'), # Waiting for delivery
        ('ready', 'Ready'), # Ready for transfer
        ('delivering', 'Delivering'), # In delivering phase
        ('done', 'Done'), # Delivered or closed XXX manage partial delivery
        ('dropshipped', 'Dropshipped'), # Order dropshipped
        ('unificated', 'Unificated'), # Unificated with another

        ('error', 'Error order'), # Order without line
        ('cancel', 'Cancel'), # Removed order
        ], 'Logistic state', default='draft',
        )

class SaleOrderLine(models.Model):
    """ Model name: Sale Order Line
    """

    _inherit = 'sale.order.line'

    # -------------------------------------------------------------------------
    #                           UTILITY:
    # -------------------------------------------------------------------------
    @api.model
    def logistic_check_ready_order(self, sale_lines=None):
        ''' Mask as done sale order with all ready lines
            if not present find all order in pending state
        '''
        order_pool = self.env['sale.order']
        if sale_lines:
            # Start from sale order line:
            order_checked = []
            for line in sale_lines:
                order = line.order_id
                if order in order_checked:
                    continue

                # Check sale.order logistic status (once):
                order.logistic_check_and_set_ready()
                order_checked.append(order)
        else:
            # Check pending order:
            orders = order_pool.search([('logistic_state', '=', 'pending')])
            return orders.logistic_check_and_set_ready() # IDs order updated
        return True

    @api.model
    def return_order_line_list_view(self, line_ids):
        ''' Return order line tree view (selected)
        '''
        # Gef view
        model_pool = self.env['ir.model.data']
        tree_view_id = model_pool.get_object_reference(
            'tyres_logistic_management',
            'view_sale_order_line_logistic_tree')[1]
        form_view_id = model_pool.get_object_reference(
            'tyres_logistic_management',
            'view_sale_order_line_logistic_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Updated lines'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'sale.order.line',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': self.env.context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    #                           UNDO Procedure:
    # -------------------------------------------------------------------------
    @api.multi
    def unlink_for_undo(self):
        ''' Undo will unlink all document linked to this line
        '''
        # TODO: Order has no pending delivery when unlink call!
        company_pool = self.env['res.company']
        header = 'SKU|QTA|PREZZO|CODICE FORNITORE|RIF. DOC.|DATA\r\n'
        row_mask = '%s|%s|%s|%s|%s|%s\r\n'
        now = fields.Datetime.now()

        # Parameter:
        company = company_pool.search([])[0]
        logistic_root_folder = os.path.expanduser(company.logistic_root_folder)
        path = os.path.join(logistic_root_folder, 'delivery')
        try:
            os.system('mkdir -p %s' % path)
        except:
            _logger.error('Cannot create %s' % path)

        order = self.order_id
        comment = _('Unlink order line: %s x %s<br/>') % (
            self.product_id.default_code,
            self.product_uom_qty,
            )

        # ---------------------------------------------------------------------
        # Purchase pre-selection:
        # ---------------------------------------------------------------------
        self.purchase_split_ids.unlink()
        comment += _('Unlink pre-assigned purchase line [#%s]<br/>') % len(
            self.purchase_split_ids)

        # ---------------------------------------------------------------------
        # Check BF
        # ---------------------------------------------------------------------
        if self.load_line_ids:
            comment += _(
                'Load internal stock with internal/delivered q [#%s]<br/>'
                    ) % len(self.load_line_ids)

            pickings = {}

            # -----------------------------------------------------------------
            # Collect data for picking:
            # -----------------------------------------------------------------
            for line in self.load_line_ids: # BF or Internal
                picking_id = line.picking_id.id or ''
                if picking_id not in pickings:
                    pickings[picking_id] = []
                pickings[picking_id].append(line)

            # -----------------------------------------------------------------
            # Write file with picking:
            # -----------------------------------------------------------------
            for picking_id in pickings:
                order_file = os.path.join(
                    path, 'pick_undo_%s.csv' % picking_id) # XXX Name with undo
                if os.path.isfile(order_file): # File yet present
                    order_file = open(order_file, 'a')
                else: # New file:
                    order_file = open(order_file, 'w')
                    order_file.write(header)

                for line in pickings[picking_id]:
                    order_file.write(row_mask % (
                        line.product_id.default_code,
                        line.product_qty,
                        line.price_unit, # TODO Check!!!
                        '', # No product code=undo
                        'undo order', # Order ref.
                        company_pool.formatLang(now, date=True),
                        ))
                order_file.close()

            # Check if procedure if fast to confirm reply (instead scheduled!):
            #self.check_import_reply() # Needed?

            # Remove all lines:
            self.load_line_ids.write({
                'state': 'draft',
                })
            self.load_line_ids.unlink()
            comment += _('Remove delivery/internal line in Pick IN doc.<br/>')

        else:
            comment += _('Not pick IN doc.<br/>')

        # ---------------------------------------------------------------------
        # Check Purchase order:
        # ---------------------------------------------------------------------
        comment += _('Remove purchase line [#%s].') % len(
            self.purchase_line_ids)
        self.purchase_line_ids.unlink()

        # Log operation:
        order.write_log_chatter_message(comment)

        return self.write({
            'undo_returned': False,
            'logistic_state': 'draft',
            })

    # -------------------------------------------------------------------------
    #                           BUTTON EVENT:
    # -------------------------------------------------------------------------
    @api.multi
    def dummy(self):
        '''Do nothing
        '''
        return True

    @api.multi
    def workflow_manual_order_line_pending(self):
        ''' When order are in 'order' state and all supplier will be choosen
            The operator put the order in 'pending' state to be evaluated
            and the next step create the order as setup in the line
            >> after: workflow_order_pending
        '''
        # Create purchase order and confirm (purchase action not used)
        self.order_id.workflow_manual_order_pending()

        # Return original order go in purchase:
        return {
            'type': 'ir.actions.act_window',
            'name': _('Order pending'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.order_id.id,
            'res_model': 'sale.order',
            'view_id': False,
            'views': [(False, 'form')],
            'domain': [],
            'context': self.env.context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    @api.multi
    def chain_broken_purchase_line(self):
        ''' Order undo line:
            If product ordered to supplier not delivered or in late:
            1. Delete purchase line so unlinked the future delivery
            2. Order line will be reset to 'draft' mode (check assign)
            3. Order will be recheck when triggered
        '''
        self.ensure_one()

        # Note: now it's not possibile, evaluate if necessary to reload
        # Stock with that qty:
        # 0. Has delivered Qty
        if self.load_line_ids:
            raise exceptions.UserError(
                _('Has delivered qty associated, cannot return!'))

        # 2. Unlink purchase order line:
        for line in self.purchase_line_ids:
            # Log deleted reference in purchase order:
            message = _(
                ''' Customer order: %s
                    Product: [%s] %s
                    Q. removed: %s
                    ''' % (
                        self.order_id.name,
                        self.product_id.product_tmpl_id.default_code,
                        self.product_id.name,
                        line.product_qty, # Q in order!
                        )
                )
            line.order_id.message_post(
                body=message, subtype='mt_comment')
        self.purchase_line_ids.unlink()

        # 3. Change line state and header:
        # Order will be remanaged when retrigger procedure!
        self.logistic_state = 'draft'
        self.order_id.logistic_state = 'order'
        return True

    @api.multi
    def open_view_sale_order(self):
        ''' Open order view
        '''
        view_id = False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale order'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.order_id.id,
            'res_model': 'sale.order',
            #'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', self.order_id.id)],
            #'context': self.env.context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    @api.multi
    def open_view_sale_order_product(self):
        ''' Open subsituted product
        '''
        view_id = False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Product detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.product_id.id,
            'res_model': 'product.product',
            #'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', self.product_id.id)],
            #'context': self.env.context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    @api.multi
    def open_view_sale_order_original_product(self):
        ''' Open original product
        '''
        view_id = False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Product detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.origin_product_id.id,
            'res_model': 'product.product',
            #'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', self.origin_product_id.id)],
            #'context': self.env.context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    @api.multi
    def open_view_sale_order_kit_product(self):
        ''' Open original product
        '''
        view_id = False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Product detail'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.kit_product_id.id,
            'res_model': 'product.product',
            #'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [('id', '=', self.kit_product_id.id)],
            #'context': self.env.context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    # -------------------------------------------------------------------------
    #                   WORKFLOW: [LOGISTIC OPERATION TRIGGER]
    # -------------------------------------------------------------------------
    # A. Assign available q.ty in stock assign a stock movement / quants
    @api.model
    def workflow_order_pending(self, lines=None):
        ''' Logistic phase 2:
            Order remain uncovered qty to the default supplier
            Generate purchase order to supplier linked to product
        '''
        now = fields.Datetime.now()

        # ---------------------------------------------------------------------
        # Pool used:
        # ---------------------------------------------------------------------
        sale_pool = self.env['sale.order']
        purchase_pool = self.env['purchase.order']
        purchase_line_pool = self.env['purchase.order.line']

        # Note: Update only pending order with uncovered lines
        if lines is None:
            lines = self.search([
                # Header:
                ('order_id.logistic_state', '=', 'pending'),
                # Line:
                ('logistic_state', '=', 'draft'),
                ])

        # ---------------------------------------------------------------------
        # Parameter from company:
        # ---------------------------------------------------------------------
        if lines:
            # Access company parameter from first line
            company = lines[0].order_id.company_id
        else: # No lines found:
            _logger.warning(
                'No pending line to order (could happen in undo)!')
            # TODO problem if order was yet ready, need to be chacked here!
            return True

        # ---------------------------------------------------------------------
        #                 Collect data for purchase order:
        # ---------------------------------------------------------------------
        purchase_db = {} # supplier is the key
        for line in lines:
            product = line.product_id
            order = line.order_id

            for splitted in line.purchase_split_ids:
                supplier = splitted.supplier_id

                # Update supplier purchase:
                key = (supplier, order)
                if key not in purchase_db:
                    purchase_db[key] = []
                purchase_db[key].append(splitted)

        selected_purchase = [] # ID: to return view list
        for key in purchase_db:
            supplier, order = key

            # -----------------------------------------------------------------
            # Create details:
            # -----------------------------------------------------------------
            purchase_id = False
            #is_company_partner = (supplier == company.partner_id)
            for splitted in purchase_db[key]:
                product = splitted.line_id.product_id
                line = splitted.line_id
                if not product or splitted.dropship_manage:
                    _logger.warning('No product or dropship order')
                    continue

                purchase_qty = splitted.product_uom_qty
                purchase_price = splitted.purchase_price

                # -------------------------------------------------------------
                # Create/Get header purchase.order (only if line was created):
                # -------------------------------------------------------------
                # TODO if order was deleted restore logistic_state to uncovered
                if not purchase_id:
                    partner = supplier or company.partner_id # Use company
                    new_purchase = purchase_pool.create({
                        'partner_id': partner.id,
                        'date_order': now,
                        'date_planned': now,
                        #'name': # TODO counter?
                        #'partner_ref': '',
                        #'logistic_state': 'draft',
                        })
                    purchase_id = new_purchase.id
                    selected_purchase.append(new_purchase)

                new_purchase = purchase_line_pool.create({
                    'order_id': purchase_id,
                    'product_id': product.id,
                    'name': product.name,
                    'product_qty': purchase_qty,
                    'date_planned': now,
                    'product_uom': product.uom_id.id,
                    'price_unit': purchase_price,

                    # Link to sale:
                    'logistic_sale_id': line.id, # multi line!
                    })

                # Update line state for pending receiving:
                line.logistic_state = 'ordered'

        # ---------------------------------------------------------------------
        # Confirm now purchase order:
        # ---------------------------------------------------------------------
        for purchase in selected_purchase:
            purchase.set_logistic_state_confirmed()

        # ---------------------------------------------------------------------
        # Extra operation:
        # ---------------------------------------------------------------------
        # Check if imported this or old purchase order:
        purchase_pool.purchase_internal_confirmed()

        # Return view:
        return purchase_pool.return_purchase_order_list_view(
            [item.id for item in selected_purchase])

    # -------------------------------------------------------------------------
    #                            COMPUTE FIELDS FUNCTION:
    # -------------------------------------------------------------------------
    @api.multi
    def _get_logistic_status_field(self):
        ''' Manage all data for logistic situation in sale order:
        '''
        _logger.warning('Update logistic qty fields now')
        for line in self:
            # -------------------------------------------------------------
            #                       NORMAL PRODUCT:
            # -------------------------------------------------------------
            #state = 'draft'
            product = line.product_id

            # -------------------------------------------------------------
            # OC: Ordered qty:
            # -------------------------------------------------------------
            logistic_order_qty = line.product_uom_qty

            # -------------------------------------------------------------
            # PUR: Purchase (order done):
            # -------------------------------------------------------------
            logistic_purchase_qty = 0.0

            # Purchase product:
            for purchase in line.purchase_line_ids:
                logistic_purchase_qty += purchase.product_qty
            line.logistic_purchase_qty = logistic_purchase_qty

            # -------------------------------------------------------------
            # UNC: Uncovered (to purchase) [OC - ASS - PUR]:
            # -------------------------------------------------------------
            logistic_uncovered_qty = \
                logistic_order_qty - logistic_purchase_qty
            line.logistic_uncovered_qty = logistic_uncovered_qty

            # State valuation:
            #if state != 'ready' and not logistic_uncovered_qty: # XXX
            #    state = 'ordered' # A part (or all) is order

            # -------------------------------------------------------------
            # BF: Received (loaded in stock):
            # -------------------------------------------------------------
            logistic_received_qty = 0.0
            # Purchase product:
            for move in line.load_line_ids:
                logistic_received_qty += move.product_uom_qty # TODO verify
            line.logistic_received_qty = logistic_received_qty

            # -------------------------------------------------------------
            # REM: Remain to receive [OC - ASS - BF]:
            # -------------------------------------------------------------
            logistic_remain_qty = \
                logistic_order_qty - logistic_received_qty
            line.logistic_remain_qty = logistic_remain_qty

            # State valuation:
            #if state != 'ready' and not logistic_remain_qty: # XXX
            #    state = 'ready' # All present coveder or in purchase

            # -------------------------------------------------------------
            # BC: Delivered:
            # -------------------------------------------------------------
            logistic_delivered_qty = 0.0
            for move in line.delivered_line_ids:
                logistic_delivered_qty += move.product_uom_qty #TODO verify
            line.logistic_delivered_qty = logistic_delivered_qty

            # -------------------------------------------------------------
            # UND: Undelivered (remain to pick out) [OC - BC]
            # -------------------------------------------------------------
            logistic_undelivered_qty = \
                logistic_order_qty - logistic_delivered_qty
            line.logistic_undelivered_qty = logistic_undelivered_qty

            # State valuation:
            #if not logistic_undelivered_qty: # XXX
            #    state = 'done' # All delivered to customer

    # -------------------------------------------------------------------------
    #                                   COLUMNS:
    # -------------------------------------------------------------------------
    undo_returned = fields.Boolean('Undo returned',
        help='Can unlink some operation that are present')

    # RELATION MANY 2 ONE:
    # B. Purchased:
    purchase_line_ids = fields.One2many(
        'purchase.order.line', 'logistic_sale_id', 'Linked to purchase',
        help='Supplier ordered line linked to customer\'s one',
        )
    load_line_ids = fields.One2many(
        'stock.move', 'logistic_load_id', 'Linked load to sale',
        help='Loaded movement in picking in documents',
        )

    # C. Deliver:
    delivered_line_ids = fields.One2many(
        'stock.move', 'logistic_unload_id', 'Linked to deliveder',
        help='Deliver movement in pick out documents',
        )

    # -------------------------------------------------------------------------
    #                               FUNCTION FIELDS:
    # -------------------------------------------------------------------------
    # Computed q.ty data:
    logistic_uncovered_qty = fields.Float(
        'Uncovered qty', digits=dp.get_precision('Product Price'),
        help='Qty not covered with internal stock (so to be purchased)',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_purchase_qty = fields.Float(
        'Purchase qty', digits=dp.get_precision('Product Price'),
        help='Qty order to supplier',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_received_qty = fields.Float(
        'Received qty', digits=dp.get_precision('Product Price'),
        help='Qty received with pick in delivery',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_remain_qty = fields.Float(
        'Remain qty', digits=dp.get_precision('Product Price'),
        help='Qty remain to receive to complete ordered',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_delivered_qty = fields.Float(
        'Delivered qty', digits=dp.get_precision('Product Price'),
        help='Qty deliverer  to final customer',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )
    logistic_undelivered_qty = fields.Float(
        'Not delivered qty', digits=dp.get_precision('Product Price'),
        help='Qty not deliverer to final customer',
        readonly=True, compute='_get_logistic_status_field', multi=True,
        store=False,
        )

    # State (sort of workflow):
    logistic_state = fields.Selection([
        ('draft', 'Custom order'), # Draft, customer order
        ('ordered', 'Ordered'), # Supplier order uncovered
        ('ready', 'Ready'), # Order to be picked out (all in stock)
        ('done', 'Done'), # Delivered qty (order will be closed)
        ], 'Logistic state', default='draft',
        #compute='_get_logistic_status_field', multi=True,
        )
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
