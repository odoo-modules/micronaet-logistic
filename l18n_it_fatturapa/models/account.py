#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# Copyright (C) 2014 Davide Corio <davide.corio@lsweb.it>
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
from odoo import api, models, fields
from odoo import tools
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class FatturapaFormat(models.Model):
    ''' Fattura PA Format and utility for formatting
        ['1.1.3']
    '''
    _name = 'fatturapa.format'
    _description = 'FatturaPA Format'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    @api.model
    def format_pa_date(self, value):
        ''' Date ISO format YYYY-MM-GG
        '''        
        return value

    @api.model
    def format_pa_float(self, value):
        ''' Date ISO format 0.00
        '''
        if not value or type(value) != float:
            return '0.00'
        else:
            return ('%10.2f' % value).strip()

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Description', size=128)
    code = fields.Char('Code', size=5)
    doc_part = fields.Text('Doc Part')

class FatturapaDocumentType(models.Model):
    ''' Document type (invoice, credit note):
        ['2.1.1.1'] (Startup data)
    '''
    _name = 'fatturapa.document_type'
    _description = 'FatturaPA Document Type'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Description', size=128)
    code = fields.Char('Code', size=4)

class FatturapaPaymentTerm(models.Model):
    ''' Payment term
        ['2.4.1']
    '''
    _name = 'fatturapa.payment_term'
    _description = 'FatturaPA Payment Term'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Description', size=128)
    code = fields.Char('Code', size=4)

class FatturapaPaymentMethod(models.Model):
    ''' Payment method
        ['2.4.2.2']
    '''
    _name = 'fatturapa.payment_method'
    _description = 'FatturaPA Payment Method'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Description', size=128)
    code = fields.Char('Code', size=4)

class WelfareFundType(models.Model):
    ''' Welfare fund
        ['2.1.1.7.1']
    '''
    _name = 'welfare.fund.type'
    _description = 'welfare fund type'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Name')
    description = fields.Char('Description')

class FatturapaFiscalPosition(models.Model):
    ''' Fiscal position:
        ['2.1.1.7.7', '2.2.1.14']
    '''
    _name = 'fatturapa.fiscal_position'
    _description = 'FatturaPA Fiscal Position'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    name = fields.Char('Description', size=128)
    code = fields.Char('Code', size=4)

class AccountPaymentTerm(models.Model):
    ''' Payment term
        ['2.4.2.2']
    '''
    _inherit = 'account.payment.term'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    fatturapa_pt_id = fields.Many2one(
        'fatturapa.payment_term', string='FatturaPA Payment Term')
    fatturapa_pm_id = fields.Many2one(
        'fatturapa.payment_method', string='FatturaPA Payment Method')

class ResPartner(models.Model):
    ''' Extra data for partner 
    '''
    _inherit = 'res.partner'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    # REA:
    rea_office = fields.Many2one(
        'res.country.state', string='Office Province')
    rea_code = fields.Char('REA Code', size=20)
    rea_capital = fields.Float('Capital')
    rea_member_type = fields.Selection(
        [('SU', 'Unique Member'),
         ('SM', 'Multiple Members')], 'Member Type')
    rea_liquidation_state = fields.Selection(
        [('LS', 'In liquidation'),
         ('LN', 'Not in liquidation')], 'Liquidation State')

    # Fattura PA:
    eori_code = fields.Char('EORI Code', size=20)
    license_number = fields.Char('License Code', size=20)
    # 1.2.6 RiferimentoAmministrazione
    pa_partner_code = fields.Char('PA Code for partner', size=20)
    # 1.2.1.4
    register = fields.Char('Professional Register', size=60)
    # 1.2.1.5
    register_province = fields.Many2one(
        'res.country.state', string='Register Province')
    # 1.2.1.6
    register_code = fields.Char('Register Code', size=60)
    # 1.2.1.7
    register_regdate = fields.Date('Register Registration Date')
    # 1.2.1.8
    register_fiscalpos = fields.Many2one(
        'fatturapa.fiscal_position',
        string='Register Fiscal Position')

    # -------------------------------------------------------------------------
    # Contraints:
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ('rea_code_uniq', 'unique (rea_code, company_id)',
         'The rea code code must be unique per company !'),
        ]

class ResCompany(models.Model):
    ''' Company data
    '''
    
    _inherit = 'res.company'
    
    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    fatturapa_fiscal_position_id = fields.Many2one(
        'fatturapa.fiscal_position', 'Fiscal Position',
        help='Fiscal position used by FatturaPA',
        )
    fatturapa_format_id = fields.Many2one(
        'fatturapa.format', 'Format',
        help='FatturaPA Format',
        )
    fatturapa_sequence_id = fields.Many2one(
        'ir.sequence', 'Sequence',
        help='Il progressivo univoco del file è rappresentato da una '
             'stringa alfanumerica di lunghezza massima di 5 caratteri '
             'e con valori ammessi da "A" a "Z" e da "0" a "9".',
        )
    fatturapa_art73 = fields.Boolean('Art73')
    fatturapa_pub_administration_ref = fields.Char(
        'Public Administration Reference Code', size=20,
        )
    fatturapa_rea_office = fields.Many2one('res.country.state',
        related='partner_id.rea_office', string='REA office')
    #fatturapa_rea_number = fields.Char(
    #    related='partner_id.rea_code', string='Rea Number')
    fatturapa_rea_capital = fields.Float(
        related='partner_id.rea_capital', string='Rea Capital')
    fatturapa_rea_partner = fields.Selection([
        ('SU', 'Unique Member'),
        ('SM', 'Multiple Members'),
        ], related='partner_id.rea_member_type', string='Member Type')
    fatturapa_rea_liquidation = fields.Selection([
        ('LS', 'In liquidation'),
        ('LN', 'Not in liquidation'),
        ], related='partner_id.rea_liquidation_state', 
        string='Liquidation State')
    fatturapa_tax_representative = fields.Many2one(
        'res.partner', 'Legal Tax Representative'
        )
    fatturapa_sender_partner = fields.Many2one(
        'res.partner', 'Third Party/Sender'
        )

class AccountFiscalPosition(models.Model):
    ''' Fattura PA for fiscal position
    '''
    _inherit = 'account.fiscal.position'
    
    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    fatturapa = fields.Boolean('Fattura PA')

class AccountTax(models.Model):
    ''' Account tax fattura PA data
    '''
    _inherit = 'account.tax'

    # -------------------------------------------------------------------------
    #                             COLUMNS:
    # -------------------------------------------------------------------------
    non_taxable_nature = fields.Selection([
        ('N1', 'escluse ex art. 15'),
        ('N2', 'non soggette'),
        ('N3', 'non imponibili'),
        ('N4', 'esenti'),
        ('N5', 'regime del margine'),
        ('N6', 'inversione contabile (reverse charge)'),
        ], string="Non taxable nature")
    payability = fields.Selection([
        ('I', 'Immediate payability'),
        ('D', 'Deferred payability'),
        ('S', 'Split payment'),
        ], string="VAT payability")
    law_reference = fields.Char(
        'Law reference', size=128)

    """@api.model
    def get_tax_by_invoice_tax(self, invoice_tax):
        if ' - ' in invoice_tax:
            tax_descr = invoice_tax.split(' - ')[0]
            tax_ids = self.search(cr, uid, [
                ('description', '=', tax_descr),
                ], context=context)
            if not tax_ids:
                raise orm.except_orm(
                    _('Error'), _('No tax %s found') %
                    tax_descr)
            if len(tax_ids) > 1:
                raise orm.except_orm(
                    _('Error'), _('Too many tax %s found') %
                    tax_descr)
        else:
            tax_name = invoice_tax
            tax_ids = self.search(cr, uid, [
                ('name', '=', tax_name),
                ], context=context)
            if not tax_ids:
                raise orm.except_orm(
                    _('Error'), _('No tax %s found') %
                    tax_name)
            if len(tax_ids) > 1:
                raise orm.except_orm(
                    _('Error'), _('Too many tax %s found') %
                    tax_name)
        return tax_ids[0]"""
        
class StockPicking(models.Model):
    ''' Stock picking extract
    '''
    _inherit = 'stock.picking'

    # TODO create fields for write DDT / Invoice lines:

    # -------------------------------------------------------------------------
    # Default path (to be overrided)
    # -------------------------------------------------------------------------
    @api.multi
    def get_default_folder_xml_invoice(self):
        '''
        '''
        path = os.path.expanduser('~/Account/Invoice/XML')
        os.system('mkdir -p %s' % path)
        return path

    # -------------------------------------------------------------------------
    # Electronic Invoice extract:
    # -------------------------------------------------------------------------
    @api.multi
    def extract_account_electronic_invoice(self):
        ''' Extract electronic invoice (or interchange file)
        '''
        # Parameter:
        company_pool = self.env['res.company']
        company = company_pool.search([])[0]
        
        format_param = company.fatturapa_format_id
        newline = '\n'        
        doc_part = format_param.doc_part + newline
        
        # ---------------------------------------------------------------------
        # Generate filename for invoice:
        # ---------------------------------------------------------------------
        # TODO
        path = self.get_default_folder_xml_invoice()

        # XXX Note: ERROR external field not declared here:
        filename = (
            '%s.xml' % (self.invoice_number or 'no_number')).replace('/', '_')
        fullname = os.path.join(path, filename)
        f_invoice = open(fullname, 'w')

        # ---------------------------------------------------------------------
        #                         WRITE INVOICE:        
        # ---------------------------------------------------------------------
        # Doc part:
        f_invoice.write(doc_part)

        # ---------------------------------------------------------------------
        # Header part:
        # ---------------------------------------------------------------------
        # 1.
        f_invoice.write('<FatturaElettronicaHeader>' + newline)        
        # 1.1
        f_invoice.write(' <DatiTrasmissione>' + newline)
        # 1.1.1
        f_invoice.write('  <IdTrasmittente' + newline)
        # 1.1.1.1
        f_invoice.write('   <IdPaese' + newline)
        # TODO IR
        f_invoice.write('   </IdPaese' + newline)
        # 1.1.1.2
        f_invoice.write('   <IdCodice' + newline)
        # TODO codice fiscale     
        f_invoice.write('   </IdCodice' + newline)                
        f_invoice.write('  </IdTrasmittente' + newline)
        
        # 1.1.2
        f_invoice.write('  <ProgressivoInvio' + newline)
        # TODO numero fattura
        f_invoice.write('  </ProgressivoInvio' + newline)
        
        # 1.1.3
        f_invoice.write('  <FormatoTrasmissione' + newline)
        # TODO FPR12   (No FPA12)
        f_invoice.write('  </FormatoTrasmissione' + newline)

        # 1.1.4
        f_invoice.write('  <CodiceDestinatario' + newline)
        # TODO Cocide univoco destinatario (7 caratteri PR, 6 PA) tutti 0 alt.
        f_invoice.write('  </CodiceDestinatario' + newline)

        # ---------------------------------------------------------------------
        # 1.1.5 (alternative 1.1.6)
        #f_invoice.write('  <ContattiTrasmittente' + newline)
        # 1.1.5.1
        #f_invoice.write('   <Telefono' + newline)
        # DATI
        #f_invoice.write('   </Telefono' + newline)
        # 1.1.5.2
        #f_invoice.write('   <Email' + newline)
        # DATI
        #f_invoice.write('   </Email' + newline)

        #f_invoice.write('  </ContattiTrasmittente' + newline)
        
        # ---------------------------------------------------------------------
        # 1.1.6 (alternative 1.1.5)
        f_invoice.write('  <PECDestinatario' + newline)
        # TODO obbligatorio se non c'è CodiceDestinatario
        f_invoice.write('  </PECDestinatario' + newline)        

        f_invoice.write(' </DatiTrasmissione' + newline)

        # ---------------------------------------------------------------------
        # 1.2
        f_invoice.write(' <CedentePrestatore' + newline)

        # 1.2.1
        f_invoice.write('  <DatiAnagrafici' + newline)

        # 1.2.1.1
        f_invoice.write('   <IdFiscaleIVA' + newline)
        
        # 1.2.1.1.1
        f_invoice.write('    <IdPaese' + newline)
        # TODO IT 
        f_invoice.write('    </IdPaese' + newline)

        # 1.2.1.1.2
        f_invoice.write('    <IdCodice' + newline)
        # TODO VAT company
        f_invoice.write('    </IdCodice' + newline)
        
        f_invoice.write('   </IdFiscaleIVA' + newline)

        # 1.2.1.2
        f_invoice.write('   <CodiceFiscale' + newline)
        # TODO Codice fiscale company
        f_invoice.write('   </CodiceFiscale' + newline)

        # 1.2.1.3
        f_invoice.write('   <Anagrafica' + newline)
        
        # ---------------------------------------------------------------------
        # 1.2.1.3.1 (alternative 1.2.1.3.2   1.2.1.3.3
        f_invoice.write('    <Denominazione' + newline)
        # RAGIONE SOCIALE Company
        f_invoice.write('    </Denominazione' + newline)
        
        # ---------------------------------------------------------------------
        # 1.2.3.1.2 (altenative 1.2.1.3.1)
        #f_invoice.write('    <Nome' + newline)
        # DATI
        #f_invoice.write('    </Nome' + newline)
        # 1.2.3.1.3 (altenative 1.2.1.3.3)
        #f_invoice.write('    <Cognome' + newline)
        # DATI
        #f_invoice.write('    </Cognome' + newline)

        # 1.2.3.1.4
        #f_invoice.write('    <Titolo' + newline)
        # DATI
        #f_invoice.write('    </Titolo' + newline)
        
        # 1.2.3.1.5
        #f_invoice.write('    <CodEORI' + newline)
        # DATI
        #f_invoice.write('    </CodEORI' + newline)

        f_invoice.write('   </Anagrafica' + newline)

        # 1.2.1.4
        #f_invoice.write('   <AlboProfessionale' + newline)
        # DATA
        #f_invoice.write('   </AlboProfessionale' + newline)

        # 1.2.1.5
        #f_invoice.write('   <ProvinciaAlbo' + newline)
        # DATA
        #f_invoice.write('   </ProvinciaAlbo' + newline)

        # 1.2.1.6
        #f_invoice.write('   <NumeroIscrizioneAlbo' + newline)
        # DATA
        #f_invoice.write('   </NumeroIscrizioneAlbo' + newline)

        # 1.2.1.7
        #f_invoice.write('   <DataIscrizioneAlbo' + newline)
        # DATA
        #f_invoice.write('   </DataIscrizioneAlbo' + newline)

        # 1.2.1.8
        f_invoice.write('   <RegimeFiscale' + newline)
        # TODO TABELLA: RF01
        f_invoice.write('   </RegimeFiscale' + newline)

        f_invoice.write('  </DatiAnagrafici' + newline)

        # 1.2.2
        f_invoice.write('  <Sede' + newline)
        
        # 1.2.2.1
        f_invoice.write('   <Indirizzo' + newline)
        # TODO
        f_invoice.write('   </Indirizzo' + newline)

        # 1.2.2.2
        f_invoice.write('   <NumeroCivico' + newline)
        # TODO
        f_invoice.write('   </NumeroCivico' + newline)

        # 1.2.2.3
        f_invoice.write('   <CAP' + newline)
        # TODO
        f_invoice.write('   </CAP' + newline)

        # 1.2.2.4
        f_invoice.write('   <Comune' + newline)
        # TODO
        f_invoice.write('   </Comune' + newline)

        # 1.2.2.5
        f_invoice.write('   <Provincia' + newline)
        # TODO
        f_invoice.write('   </Provincia' + newline)

        # 1.2.2.6
        f_invoice.write('   <Nazione' + newline)
        # TODO
        f_invoice.write('   </Nazione' + newline)

        f_invoice.write('  </Sede' + newline)

        # ---------------------------------------------------------------------
        # IF PRESENT:
        # 1.2.3
        #f_invoice.write('  <StabileOrganizzazione' + newline)
        
        # 1.2.3.1
        #f_invoice.write('   <Indirizzo' + newline)
        # DATA
        #f_invoice.write('   </Indirizzo' + newline)

        # 1.2.3.2
        #f_invoice.write('   <NumeroCivico' + newline)
        # DATA
        #f_invoice.write('   </NumeroCivico' + newline)

        # 1.2.3.3
        #f_invoice.write('   <CAP' + newline)
        # DATA
        #f_invoice.write('   </CAP' + newline)

        # 1.2.3.4
        #f_invoice.write('   <Comune' + newline)
        # DATA
        #f_invoice.write('   </Comune' + newline)

        # 1.2.3.5
        #f_invoice.write('   <Provincia' + newline)
        # DATA
        #f_invoice.write('   </Provincia' + newline)

        # 1.2.3.6
        #f_invoice.write('   <Nazione' + newline)
        # DATA
        #f_invoice.write('   </Nazione' + newline)

        #f_invoice.write('  </StabileOrganizzazione' + newline)
        # ---------------------------------------------------------------------

        # 1.2.4
        f_invoice.write('  <IscrizioneREA' + newline)
        
        # 1.2.4.1
        f_invoice.write('   <Ufficio' + newline)
        # TODO
        f_invoice.write('   </Ufficio' + newline)

        # 1.2.4.2
        f_invoice.write('   <NumeroREA' + newline)
        # TODO
        f_invoice.write('   </NumeroREA' + newline)

        # 1.2.4.3  (0.1)
        #f_invoice.write('   <CapitaleSociale' + newline)
        # TODO
        #f_invoice.write('   </CapitaleSociale' + newline)

        # 1.2.4.3  (0.1)
        #f_invoice.write('   <SocioUnico' + newline)
        # TODO
        #f_invoice.write('   </SocioUnico' + newline)
       
        # 1.2.4.3  (0.1)
        f_invoice.write('   <StatoLiquidazione' + newline)
        # TODO
        f_invoice.write('   </StatoLiquidazione' + newline)
       
        f_invoice.write('  </IscrizioneREA' + newline)
        
        # ---------------------------------------------------------------------
        # NOT MANDATORY:
        # 1.2.5
        #f_invoice.write('  <Contatti' + newline)
        
        # 1.2.5.1
        #f_invoice.write('   <Telefono' + newline)
        # DATA
        #f_invoice.write('   </Telefono' + newline)

        # 1.2.5.2
        #f_invoice.write('   <Fax' + newline)
        # DATA
        #f_invoice.write('   </Fax' + newline)

        # 1.2.5.2
        #f_invoice.write('   <Email' + newline)
        # DATA
        #f_invoice.write('   </Email' + newline)

        #f_invoice.write('  </Contatti' + newline)
        # ---------------------------------------------------------------------
        
        # ---------------------------------------------------------------------
        # NOT MANDATORY:
        # 1.2.6 RiferimentoAmministrazione
        
        # ---------------------------------------------------------------------
        # NOT MANDATORY:
        # 1.3 RappresentanteFiscale
        # 1.3.1 DatiAnagrafici
        # 1.3.1.1 IdFiscaleIVA
        # 1.3.1.1.1 IdPaese
        # 1.3.1.1.2 Idcodice
        # 1.3.1.2 CodiceFiscale
        # 1.3.1.3 Anagrafica
        # 1.3.1.3.1 Denominazione
        # 1.3.1.3.2 Nome
        # 1.3.1.3.3 Cognome
        # 1.3.1.3.4 Titolo
        # 1.3.1.3.5 CodEORI

        f_invoice.write(' </CedentePrestatore' + newline)
        
        # 1.4
        f_invoice.write(' <CessionarioCommittente' + newline)

        # 1.4.1
        f_invoice.write('  <DatiAnagrafici' + newline)

        # Alternativo al blocco 1.4.1.2 ---------------------------------------
        # 1.4.1.1
        f_invoice.write('   <IdFiscaleIVA' + newline)
        
        # 1.4.1.1.1
        f_invoice.write('    <IdPaese' + newline)
        # TODO IT cliente
        f_invoice.write('    </IdPaese' + newline)

        # 1.4.1.1.2
        f_invoice.write('    <IdCodice' + newline)
        # TODO Codice fiscale cliente
        f_invoice.write('    </IdCodice' + newline)
        
        f_invoice.write('   </IdFiscaleIVA' + newline)

        # Alternativo al blocco 1.4.1.1 ---------------------------------------
        # 1.4.1.2
        f_invoice.write('   <CodiceFiscale' + newline)
        # TODO        
        f_invoice.write('   </CodiceFiscale' + newline)

        # 1.4.1.3
        f_invoice.write('   <Anagrafica' + newline)
        
        # ---------------------------------------------------------------------
        # 1.4.1.3.1 (alternative 1.2.1.3.2   1.2.1.3.3
        f_invoice.write('    <Denominazione' + newline)
        # TODO Ragione sociale
        f_invoice.write('    </Denominazione' + newline)
        
        # ---------------------------------------------------------------------
        # 1.4.3.1.2 (altenative 1.2.1.3.1)
        f_invoice.write('    <Nome' + newline)
        # TODO
        f_invoice.write('    </Nome' + newline)
        # 1.4.3.1.3 (altenative 1.2.1.3.3)
        f_invoice.write('    <Cognome' + newline)
        # TODO
        f_invoice.write('    </Cognome' + newline)

        # 1.4.3.1.4
        #f_invoice.write('    <Titolo' + newline)
        # DATI
        #f_invoice.write('    </Titolo' + newline)
        
        # 1.4.3.1.5
        #f_invoice.write('    <CodEORI' + newline)
        # DATI
        #f_invoice.write('    </CodEORI' + newline)

        f_invoice.write('   </Anagrafica' + newline)

        # ---------------------------------------------------------------------
        # 1.4.2
        f_invoice.write('  <Sede' + newline)
        
        # 1.4.2.1
        f_invoice.write('   <Indirizzo' + newline)
        # TODO
        f_invoice.write('   </Indirizzo' + newline)

        # 1.4.2.2
        f_invoice.write('   <NumeroCivico' + newline)
        # TODO
        f_invoice.write('   </NumeroCivico' + newline)

        # 1.4.2.3
        f_invoice.write('   <CAP' + newline)
        # TODO
        f_invoice.write('   </CAP' + newline)

        # 1.4.2.4
        f_invoice.write('   <Comune' + newline)
        # TODO
        f_invoice.write('   </Comune' + newline)

        # 1.4.2.5
        f_invoice.write('   <Provincia' + newline)
        # TODO
        f_invoice.write('   </Provincia' + newline)

        # 1.4.2.6
        f_invoice.write('   <Nazione' + newline)
        # TODO
        f_invoice.write('   </Nazione' + newline)

        f_invoice.write('  </Sede' + newline)

        # ---------------------------------------------------------------------
        # IF PRESENT:
        # 1.4.3
        #f_invoice.write('  <StabileOrganizzazione' + newline)
        
        # 1.4.3.1
        #f_invoice.write('   <Indirizzo' + newline)
        # DATA
        #f_invoice.write('   </Indirizzo' + newline)

        # 1.4.3.2
        #f_invoice.write('   <NumeroCivico' + newline)
        # DATA
        #f_invoice.write('   </NumeroCivico' + newline)

        # 1.4.3.3
        #f_invoice.write('   <CAP' + newline)
        # DATA
        #f_invoice.write('   </CAP' + newline)

        # 1.4.3.4
        #f_invoice.write('   <Comune' + newline)
        # DATA
        #f_invoice.write('   </Comune' + newline)

        # 1.4.3.5
        #f_invoice.write('   <Provincia' + newline)
        # DATA
        #f_invoice.write('   </Provincia' + newline)

        # 1.4.3.6
        #f_invoice.write('   <Nazione' + newline)
        # DATA
        #f_invoice.write('   </Nazione' + newline)

        #f_invoice.write('  </StabileOrganizzazione' + newline)
        # ---------------------------------------------------------------------

        # NOT MANDATORY:
        # 1.4.4 RappresentanteFiscale
        # 1.4.4.1 IdFiscaleIVA
        # 1.4.4.1.1 IdPaese
        # 1.4.4.1.2 IdCodice
        # 1.4.4.2 Denominazione
        # 1.4.4.3 Nome
        # 1.4.4.4 Cognome

        f_invoice.write('  </DatiAnagrafici' + newline)
        f_invoice.write(' </CessionarioCommittente' + newline)

        # NOT MANDATORY:
        # 1.5 TerzoIntermediarioOSoggettoEmittente
        # 1.5.1 DatiAnagrafici
        # 1.5.1.1 IdFiscaleIVA
        # 1.5.1.1.1 IdPaese
        # 1.5.1.1.2 IdCodice
        # 1.5.1.2 CodiceFiscale
        # 1.5.1.3 Anagrafica
        # 1.5.1.3.1 Denominazione
        # 1.5.1.3.2 Nome
        # 1.5.1.3.3 Cognome
        # 1.5.1.3.4 Titolo
        # 1.5.1.3.5 CodEORI

        # NOT MANDATORY:
        # 1.6 SoggettoEmittente
        
        f_invoice.write('</FatturaElettronicaHeader' + newline)
        # ---------------------------------------------------------------------

        # ---------------------------------------------------------------------
        #                                BODY:
        # ---------------------------------------------------------------------
        # 2.
        f_invoice.write('<FatturaElettronicaBody' + newline)
        
        # 2.1
        f_invoice.write(' <DatiGenerali' + newline)
        
        # 2.1.1
        f_invoice.write('  <DatiGeneraliDocumento' + newline)

        # 2.1.1.1
        f_invoice.write('   <TipoDocumento' + newline)
        # TODO Usare la tabella TD01 Fattura TD04 Nota di credito
        f_invoice.write('   </TipoDocumento' + newline)

        # 2.1.1.2
        f_invoice.write('   <Divisa' + newline)
        # TODO EUR
        f_invoice.write('   </Divisa' + newline)

        # 2.1.1.3
        f_invoice.write('   <Data' + newline)
        # TODO Data fattura ISO format YYYY-MM-DD
        f_invoice.write('   </Data' + newline)

        # 2.1.1.4
        f_invoice.write('   <Numero' + newline)
        # TODO Serie - Numero
        f_invoice.write('   </Numero' + newline)

        # 2.1.1.5
        #f_invoice.write('   <DatiRitenuta' + newline)
        # 2.1.1.5.1 TipoRitenuta
        # 2.1.1.5.1 ImportoRitenuta
        # 2.1.1.5.1 AliquotaRitenuta
        # 2.1.1.5.1 CausaleRitenuta
        #f_invoice.write('   </DatiRitenuta' + newline)

        # TODO Valutare questione bollo:
        # 2.1.1.6
        f_invoice.write('   <DatiBollo' + newline)        
        
        # 2.1.1.6.1 
        f_invoice.write('    <BolloVirtuale' + newline)        
        # TODO
        f_invoice.write('    </BolloVirtuale' + newline)        

        # 2.1.1.6.2
        f_invoice.write('    <ImportoBollo' + newline)        
        # TODO
        f_invoice.write('    </ImportoBollo' + newline)        

        f_invoice.write('   </DatiBollo' + newline)

        # 2.1.1.7 DatiCassaPrevidenziale
        # 2.1.1.7.1 TipoCassa
        # 2.1.1.7.2 AlCassa
        # 2.1.1.7.3 ImportoContributoCassa
        # 2.1.1.7.4 ImponibileCassa
        # 2.1.1.7.5 AliquotaIVA
        # 2.1.1.7.6 Ritenuta
        # 2.1.1.7.7 Natura
        # 2.1.1.7.8 RiferimentoAmministrazione

        # ---------------------------------------------------------------------
        # VALUTARE: Abbuoni attivi / passivi:
        # 2.1.1.8
        f_invoice.write('   <ScontoMaggiorazione' + newline)        
        
        # 2.1.1.8.1 
        f_invoice.write('    <Tipo' + newline)        
        # TODO
        f_invoice.write('    </Tipo' + newline)        

        # ---------------------------------------------------------------------
        # 2.1.1.8.2     >>> Alternative 2.1.1.8.3
        f_invoice.write('    <Percentuale' + newline)        
        # TODO
        f_invoice.write('    </Percentuale' + newline)        

        # ---------------------------------------------------------------------
        # 2.1.1.8.3     >>> Alternative 2.1.1.8.2
        f_invoice.write('    <Importo' + newline)        
        # TODO
        f_invoice.write('    </Importo' + newline)        

        f_invoice.write('   </ScontoMaggiorazione' + newline)        
        
        # 2.1.1.9
        f_invoice.write('   <ImportoTotaleDocumento' + newline)        
        # TODO Totale IVATO (al netto di sconti)
        f_invoice.write('   </ImportoTotaleDocumento' + newline)        
        
        # 2.1.1.10
        f_invoice.write('   <Arrotondamento' + newline)        
        # TODO
        f_invoice.write('   </Arrotondamento' + newline)        

        # 2.1.1.11
        f_invoice.write('   <Causale' + newline)        
        # TODO Causale del documento (testo)
        f_invoice.write('   </Causale' + newline)        

        # 2.1.1.12
        #f_invoice.write('   <Art73' + newline)        
        # TODO
        #f_invoice.write('   </Art73' + newline)        
        
        f_invoice.write('  </DatiGeneraliDocumento' + newline)

        # ---------------------------------------------------------------------        
        # RIFERIMENTO ORDINE:
        # ---------------------------------------------------------------------        
        # 2.1.2
        f_invoice.write('  <DatiOrdineAcquisto' + newline)
        
        # 2.1.2.1 
        f_invoice.write('   <RiferimentoNumeroLinea' + newline)
        # DATA
        f_invoice.write('   </RiferimentoNumeroLinea' + newline)

        # 2.1.2.2
        f_invoice.write('   <IdDocumento' + newline)
        # DATA
        f_invoice.write('   </IdDocumento' + newline)

        # 2.1.2.3 
        f_invoice.write('   <Data' + newline)
        # DATA
        f_invoice.write('   </Data' + newline)

        # 2.1.2.4 
        f_invoice.write('   <NumItem' + newline)
        # DATA
        f_invoice.write('   </NumItem' + newline)

        # 2.1.2.5 
        f_invoice.write('   <CodiceCommessaConvenzione' + newline)
        # DATA
        f_invoice.write('   </CodiceCommessaConvenzione' + newline)

        # NOT MANDATORI: PA only:
        # 2.1.2.6 
        #f_invoice.write('   <CodiceCUP' + newline)
        # DATA
        #f_invoice.write('   </CodiceCUP' + newline)
        # 2.1.2.7 
        #f_invoice.write('   <CodiceCIG' + newline)
        # DATA
        #f_invoice.write('   </CodiceCIG' + newline)
 
        f_invoice.write('  </DatiOrdineAcquisto' + newline)
        # ---------------------------------------------------------------------        

        # ---------------------------------------------------------------------        
        # RIFERIMENTO CONTRATTO:
        # ---------------------------------------------------------------------        
        # 2.1.3
        f_invoice.write('   <DatiContratto' + newline)
        # DATA
        f_invoice.write('   </DatiContratto' + newline)

        # 2.1.4
        f_invoice.write('   <DatiConvenzione' + newline)
        # DATA
        f_invoice.write('   </DatiConvenzione' + newline)

        # 2.1.5
        f_invoice.write('   <DatiRicezione' + newline)
        # DATA
        f_invoice.write('   </DatiRicezione' + newline)

        # 2.1.6
        f_invoice.write('   <DatiFattureCollegate' + newline)
        # DATA
        f_invoice.write('   </DatiFattureCollegate' + newline)

        # 2.1.7
        f_invoice.write('   <DatiSAL' + newline)
        
        # 2.1.7.1
        f_invoice.write('    <RiferimenntoFase' + newline)
        # DATA 
        f_invoice.write('    </RiferimenntoFase' + newline)
        
        f_invoice.write('   </DatiSAL' + newline)
        # ---------------------------------------------------------------------        

        # ---------------------------------------------------------------------        
        # RIFERIMENTO DDT:
        # ---------------------------------------------------------------------        
        # 2.1.8
        f_invoice.write('   <DatiDDT' + newline)
        
        # 2.1.8.1 
        f_invoice.write('    <NumeroDDT' + newline)
        # TODO Numero documento
        f_invoice.write('    </NumeroDDT' + newline)
                    
        # 2.1.8.2
        f_invoice.write('    <DataDDT' + newline)
        # TODO ISO   
        f_invoice.write('    </DataDDT' + newline)

        # 2.1.8.3
        f_invoice.write('    <RiferimentoNumeroLinea' + newline)
        # TODO Numero linea                   
        f_invoice.write('    </RiferimentoNumeroLinea' + newline)
        
        f_invoice.write('   </DatiDDT' + newline)
        # ---------------------------------------------------------------------        

        # ---------------------------------------------------------------------        
        # FATTURA ACCOMPAGNATORIA:
        # ---------------------------------------------------------------------        
        """
        # 2.1.9
        f_invoice.write('   <DatiTrasporto' + newline)
        
        # 2.1.9.1
        f_invoice.write('    <DatiAnagraficiVettore' + newline)

        # 2.1.9.1.1
        f_invoice.write('    <IdFiscaleIVA' + newline)
        
        # 2.1.9.1.1.1
        f_invoice.write('     <IdPaese' + newline)
        # DATI
        f_invoice.write('     </IdPaese' + newline)

        # 2.1.9.1.1.2
        f_invoice.write('     <IdCodice' + newline)
        # DATI
        f_invoice.write('     </IdCodice' + newline)
        
        f_invoice.write('    </IdFiscaleIVA' + newline)

        # 2.1.9.1.2
        f_invoice.write('    <CodiceFiscale' + newline)
        # DATA        
        f_invoice.write('    </CodiceFiscale' + newline)

        # 2.1.9.1.3
        f_invoice.write('    <Anagrafica' + newline)
        
        # ---------------------------------------------------------------------
        # 2.1.9.1.3.1 (alternative 2.1.9.1.3.2    2.1.9.1.3.3
        f_invoice.write('     <Denominazione' + newline)
        # DATI
        f_invoice.write('     </Denominazione' + newline)
        
        # ---------------------------------------------------------------------
        # 2.1.9.1.3.2 (altenative 2.1.9.1.3.1)
        f_invoice.write('     <Nome' + newline)
        # DATI
        f_invoice.write('     </Nome' + newline)
        # 2.1.9.1.3.3 (altenative 1.2.1.3.3)
        f_invoice.write('     <Cognome' + newline)
        # DATI
        f_invoice.write('     </Cognome' + newline)

        # 2.1.9.1.3.4
        #f_invoice.write('     <Titolo' + newline)
        # DATI
        #f_invoice.write('     </Titolo' + newline)
        
        # 2.1.9.1.3.5
        #f_invoice.write('     <CodEORI' + newline)
        # DATI
        #f_invoice.write('     </CodEORI' + newline)

        # 2.1.9.1.4
        #f_invoice.write('    <NumeroLicenzaGuida' + newline)
        # DATA        
        #f_invoice.write('    </NumeroLicenzaGuida' + newline)

        f_invoice.write('    </Anagrafica' + newline)

        f_invoice.write('    </DatiAnagraficiVettore' + newline)

        # 2.1.9.2
        f_invoice.write('    <MezzoTrasporto' + newline)
        # DATA
        f_invoice.write('    </MezzoTrasporto' + newline)

        # 2.1.9.3
        f_invoice.write('    <CausaleTrasporto' + newline)
        # DATA
        f_invoice.write('    </CausaleTrasporto' + newline)

        # 2.1.9.4
        f_invoice.write('    <NumeroColli' + newline)
        # DATA
        f_invoice.write('    </NumeroColli' + newline)

        # 2.1.9.5
        f_invoice.write('    <Descrizione' + newline)
        # DATA
        f_invoice.write('    </Descrizione' + newline)

        # 2.1.9.6
        f_invoice.write('    <UnitaMisuraPeso' + newline)
        # DATA
        f_invoice.write('    </UnitaMisuraPeso' + newline)

        # 2.1.9.7
        f_invoice.write('    <PesoLordo' + newline)
        # DATA
        f_invoice.write('    </PesoLordo' + newline)

        # 2.1.9.8
        f_invoice.write('    <PesoNetto' + newline)
        # DATA
        f_invoice.write('    </PesoNetto' + newline)

        # 2.1.9.9
        f_invoice.write('    <DataOraRitiro' + newline)
        # DATA
        f_invoice.write('    </DataOraRitiro' + newline)

        # 2.1.9.10
        f_invoice.write('    <DataInizioTrasporto' + newline)
        # DATA
        f_invoice.write('    </DataInizioTrasporto' + newline)

        # 2.1.9.11
        f_invoice.write('    <TipoResa' + newline)
        # DATA
        f_invoice.write('    </TipoResa' + newline)

        # ---------------------------------------------------------------------
        # 2.1.9.12
        f_invoice.write('   <IndirizzoResa' + newline)
        
        # 2.1.9.12.1
        f_invoice.write('    <Indirizzo' + newline)
        # DATA
        f_invoice.write('    </Indirizzo' + newline)

        # 2.1.9.12.2
        f_invoice.write('    <NumeroCivico' + newline)
        # DATA
        f_invoice.write('    </NumeroCivico' + newline)

        # 2.1.9.12.3
        f_invoice.write('    <CAP' + newline)
        # DATA
        f_invoice.write('    </CAP' + newline)

        # 2.1.9.12.4
        f_invoice.write('    <Comune' + newline)
        # DATA
        f_invoice.write('    </Comune' + newline)

        # 2.1.9.12.5
        f_invoice.write('    <Provincia' + newline)
        # DATA
        f_invoice.write('    </Provincia' + newline)

        # 2.1.9.12.6
        f_invoice.write('    <Nazione' + newline)
        # DATA
        f_invoice.write('    </Nazione' + newline)
                
        f_invoice.write('   </IndirizzoResa' + newline)
        # ---------------------------------------------------------------------

        # 2.1.9.13
        f_invoice.write('    <DataOraConsegna' + newline)
        # DATA
        f_invoice.write('    </DataOraConsegna' + newline)

        f_invoice.write('   </DatiTrasporto' + newline)

        # ---------------------------------------------------------------------
        # NOT MANADATORY: Agevolazione trasportatore:
        # 2.1.10
        f_invoice.write('   <FatturaPrincipale' + newline)        
        
        # 2.1.10.1
        f_invoice.write('    <NumeroFatturaPrincipale' + newline)        
        # DATA
        f_invoice.write('    </NumeroFatturaPrincipale' + newline)

        # 2.1.10.2
        f_invoice.write('    <DataFatturaPrincipale' + newline)        
        # DATA
        f_invoice.write('    </DataFatturaPrincipale' + newline)

        f_invoice.write('   </FatturaPrincipale' + newline)
        # ---------------------------------------------------------------------
        
        f_invoice.write(' </DatiGenerali' + newline)
        """
        # ---------------------------------------------------------------------        


        # 2.2
        f_invoice.write(' <DatiBeniServizi' + newline)

        # 2.2.1
        f_invoice.write('  <DettaglioLinee' + newline)

        # 2.2.1.1
        f_invoice.write('   <NumeroLinea' + newline)
        # TODO 
        f_invoice.write('   </NumeroLinea' + newline)

        # Spesa accessoria (condizionale):
        # 2.2.1.2 # Solo se SC PR AB AC (spesa accessoria)
        f_invoice.write('   <TipoCessionePrestazione' + newline)
        # TODO AB(uono)  AC(essoria)  SC(onto) PR(remio)
        f_invoice.write('   </TipoCessionePrestazione' + newline)

        # 2.2.1.3
        f_invoice.write('   <CodiceArticolo' + newline)

        # 2.2.1.3.1 # PROPRIETARIO EAN TARIC SSC
        f_invoice.write('    <CodiceTipo' + newline)
        # TODO PROPRIETARIO o EAN (o altri)
        f_invoice.write('    </CodiceTipo' + newline)

        # 2.2.1.3.2 # come da punto precedente
        f_invoice.write('    <CodiceValore' + newline)
        # TODO CODICE
        f_invoice.write('    </CodiceValore' + newline)

        f_invoice.write('   </CodiceArticolo' + newline)

        # 2.2.1.4
        f_invoice.write('   <Descrizione' + newline)
        # TODO 
        f_invoice.write('   </Descrizione' + newline)

        # 2.2.1.5
        f_invoice.write('   <Quantita' + newline)
        # TODO
        f_invoice.write('   </Quantita' + newline)

        # 2.2.1.6
        f_invoice.write('   <UnitaMisura' + newline)
        # TODO 
        f_invoice.write('   </UnitaMisura' + newline)

        # Servizi: Opzionale:
        # 2.2.1.7 # Per Servizi
        #f_invoice.write('   <DataInizioPeriodo' + newline)
        # TODO
        #f_invoice.write('   </DataInizioPeriodo' + newline)

        # 2.2.1.8 # Per Servizi
        #f_invoice.write('   <DataFinePeriodo' + newline)
        # TODO
        #f_invoice.write('   </DataFinePeriodo' + newline)

        # 2.2.1.9 # Anche negativo # Vedi 2.2.1.2
        f_invoice.write('   <PrezzoUnitario' + newline)
        # TODO prezzo unitario, totale sconto (anche negativo)
        f_invoice.write('   </PrezzoUnitario' + newline)

        # ---------------------------------------------------------------------
        # Sconto manuale (opzionale:
        # 2.2.1.10
        f_invoice.write('   <ScontoMaggiorazione' + newline)

        # 2.2.1.10.1 # SC o MG
        f_invoice.write('    <Tipo' + newline)
        f_invoice.write('    </Tipo' + newline)

        # 2.2.1.10.2 # Alternativo a 2.2.1.10.3
        f_invoice.write('    <Percentuale' + newline)
        f_invoice.write('    </Percentuale' + newline)

        # 2.2.1.10.3 # Alternativo a 2.2.1.10.2
        f_invoice.write('    <Importo' + newline)
        f_invoice.write('    </Importo' + newline)

        f_invoice.write('   </ScontoMaggiorazione' + newline)
        # ---------------------------------------------------------------------


        # 2.2.1.11
        f_invoice.write('   <PrezzoTotale' + newline)
        # TODO Subtotale
        f_invoice.write('   </PrezzoTotale' + newline)

        # 2.2.1.12
        f_invoice.write('   <AliquotaIVA' + newline)
        # TODO percentuale 22.00
        f_invoice.write('   </AliquotaIVA' + newline)

        # 2.2.1.13
        #f_invoice.write('   <Ritenuta' + newline)
        # TODO 
        #f_invoice.write('   </Ritenuta' + newline)

        # Se IVA 0 obbligatorio:
        # 2.2.1.14
        f_invoice.write('   <Natura' + newline)
        # TODO Descrizione eventuale esenzione
        f_invoice.write('   </Natura' + newline)

        # 2.2.1.15
        #f_invoice.write('   <RiferimentoAmministrazione' + newline)
        # TODO
        #f_invoice.write('   </RiferimentoAmministrazione' + newline)

        # 2.2.1.16
        """
        f_invoice.write('   <AltriDatiGestionali' + newline)

        # 2.2.1.16.1
        f_invoice.write('    <TipoDato' + newline)
        f_invoice.write('    </TipoDato' + newline)

        # 2.2.1.16.2
        f_invoice.write('    <RiferimentoTesto' + newline)
        f_invoice.write('    </RiferimentoTesto' + newline)

        # 2.2.1.16.3
        f_invoice.write('    <RiferimentoNumero' + newline)
        f_invoice.write('    </RiferimentoNumero' + newline)

        # 2.2.1.16.4
        f_invoice.write('    <RiferimentoData' + newline)
        f_invoice.write('    </RiferimentoData' + newline)

        f_invoice.write('   </AltriDatiGestionali' + newline)
        """
        
        f_invoice.write(' </DettaglioLinee' + newline)

        # Elenco riepilogativo IVA del documento (1:N):
        # 2.2.2
        f_invoice.write('  <DatiRiepilogo' + newline)

        # 2.2.2.1        
        f_invoice.write('   <AliquotaIVA' + newline)
        # TODO 22.00
        f_invoice.write('   </AliquotaIVA' + newline)

        # 2.2.2.2 # Tabella
        f_invoice.write('   <Natura' + newline)
        # TODO 
        f_invoice.write('   </Natura' + newline)

        # 2.2.2.3
        #f_invoice.write('   <SpeseAccessorie' + newline)
        # TODO 
        #f_invoice.write('   </SpeseAccessorie' + newline)

        # 2.2.2.4
        #f_invoice.write('   <Arrotondamento' + newline)
        # TODO 
        #f_invoice.write('   </Arrotondamento' + newline)

        # 2.2.2.5
        f_invoice.write('   <ImponibileImporto' + newline)
        # TODO Base imponibile
        f_invoice.write('   </ImponibileImporto' + newline)

        # 2.2.2.6
        f_invoice.write('   <Imposta' + newline)
        # TODO Imposta totale
        f_invoice.write('   </Imposta' + newline)

        # 2.2.2.7
        f_invoice.write('   <EsigibilitaIVA' + newline)
        # TODO I(mmediata) D(ifferita) S(cissione)
        f_invoice.write('   </EsigibilitaIVA' + newline)

        # 2.2.2.8
        f_invoice.write('   <RiferimentoNormativo' + newline)
        # Se natura valorizzato
        f_invoice.write('   </RiferimentoNormativo' + newline)

        f_invoice.write('  </DatiRiepilogo' + newline)

        f_invoice.write(' </DatiBeniServizi' + newline)

        # 2.3
        """
        f_invoice.write(' <DatiVeicoli' + newline)

        # 2.3.1
        f_invoice.write('  <Data' + newline)
        f_invoice.write('  </Data' + newline)

        # 2.3.1
        f_invoice.write('  <TotalePercorso' + newline)
        f_invoice.write('  </TotalePercorso' + newline)

        f_invoice.write(' </DatiVeicoli' + newline)
        """

        # ---------------------------------------------------------------------
        # Pagamento:
        # ---------------------------------------------------------------------
        # 2.4
        f_invoice.write(' <DatiPagamento' + newline)

        # 2.4.1
        f_invoice.write('  <CondizioniPagamento' + newline)
        # TODO tabelle TP01 a rate TP02 pagamento completo TP03 anticipo
        f_invoice.write('  </CondizioniPagamento' + newline)
        
        # Elenco rate:
        # 2.4.2
        f_invoice.write('  <DettaglioPagamento' + newline)

        # 2.4.2.1 (0.1)
        f_invoice.write('   <Beneficiario' + newline)
        # TODO se differente dal cedente
        f_invoice.write('   </Beneficiario' + newline)
        
        # 2.4.2.2
        f_invoice.write('   <ModalitaPagamento' + newline)
        # TODO Tabella MP
        f_invoice.write('   </ModalitaPagamento' + newline)
        
        # 2.4.2.3 (0.1)
        f_invoice.write('   <DataRiferimentoTerminiPagamento' + newline)
        # TODO 
        f_invoice.write('   </DataRiferimentoTerminiPagamento' + newline)
        
        # 2.4.2.4 (0.1)
        f_invoice.write('   <GiorniTerminiPagamento' + newline)
        # TODO 
        f_invoice.write('   </GiorniTerminiPagamento' + newline)
        
        # 2.4.2.5 (0.1)
        f_invoice.write('   <DataScadenzaPagamento' + newline)
        # TODO 
        f_invoice.write('   </DataScadenzaPagamento' + newline)
        
        # 2.4.2.6
        f_invoice.write('   <ImportoPagamento' + newline)
        # TODO 
        f_invoice.write('   </ImportoPagamento' + newline)

        # ---------------------------------------------------------------------
        # Ufficio postale:        
        # ---------------------------------------------------------------------
        """
        # 2.4.2.7
        f_invoice.write('   <CodUfficioPostale' + newline)
        f_invoice.write('   </CodUfficioPostale' + newline)
        
        # 2.4.2.8
        f_invoice.write('   <CognomeQuietanzante' + newline)
        f_invoice.write('   </CognomeQuietanzante' + newline)
        
        # 2.4.2.9
        f_invoice.write('   <NomeQuietanzante' + newline)
        f_invoice.write('   </NomeQuietanzante' + newline)
        
        # 2.4.2.10
        f_invoice.write('   <CFQuietanzante' + newline)
        f_invoice.write('   </CFQuietanzante' + newline)
        
        # 2.4.2.11
        f_invoice.write('   <TitoloQuietanzante' + newline)
        f_invoice.write('   </TitoloQuietanzante' + newline)
        """
        # ---------------------------------------------------------------------
        
        # 2.4.2.12 (0.1)
        f_invoice.write('   <IstitutoFinanziario' + newline)
        f_invoice.write('   </IstitutoFinanziario' + newline)
        
        # 2.4.2.13 (0.1)
        f_invoice.write('   <IBAN' + newline)
        f_invoice.write('   </IBAN' + newline)
        
        # 2.4.2.14 (0.1)
        f_invoice.write('   <ABI' + newline)
        f_invoice.write('   </ABI' + newline)
        
        # 2.4.2.15 (0.1)
        f_invoice.write('   <CAB' + newline)
        f_invoice.write('   </CAB' + newline)
        
        # 2.4.2.16 (0.1)
        f_invoice.write('   <BIC' + newline)
        f_invoice.write('   </BIC' + newline)

        # ---------------------------------------------------------------------
        # Pagamento anticipato:        
        # 2.4.2.17
        """
        f_invoice.write('   <ScontoPagamentoAnticipato' + newline)
        # TODO 
        f_invoice.write('   </ScontoPagamentoAnticipato' + newline)
        
        # 2.4.2.18
        f_invoice.write('   <DataLimitePagamentoAnticipato' + newline)
        # TODO 
        f_invoice.write('   </DataLimitePagamentoAnticipato' + newline)
        
        # 2.4.2.19
        f_invoice.write('   <PenalitaPagamentiRitardati' + newline)
        # TODO 
        f_invoice.write('   </PenalitaPagamentiRitardati' + newline)
        
        # 2.4.2.20
        f_invoice.write('   <DataDecorrenzaPenale' + newline)
        # TODO 
        f_invoice.write('   </DataDecorrenzaPenale' + newline)
        
        # 2.4.2.21
        f_invoice.write('   <CodicePagamento' + newline)
        # TODO 
        f_invoice.write('   </CodicePagamento' + newline)
        """
        # ---------------------------------------------------------------------


        f_invoice.write('  </DettaglioPagamento' + newline)
        f_invoice.write(' </DatiPagamento' + newline)
        # ---------------------------------------------------------------------


        # 2.5
        f_invoice.write(' <Allegati' + newline)

        # 2.5.1
        f_invoice.write('  <NomeAttachment' + newline)
        f_invoice.write('  </NomeAttachment' + newline)

        # 2.5.2 # ZIP RAR
        f_invoice.write('  <AlgoritmoCompressione' + newline)
        f_invoice.write('  </AlgoritmoCompressione' + newline)

        # 2.5.3 # TXT XML DOC PDF
        f_invoice.write('  <FormatoAttachment' + newline)
        f_invoice.write('  </FormatoAttachment' + newline)

        # 2.5.4
        f_invoice.write('  <DescrizioneAttachment' + newline)
        f_invoice.write('  </DescrizioneAttachment' + newline)

        # 2.5.5
        f_invoice.write('  <Attachment' + newline)
        f_invoice.write('  </Attachment' + newline)

        f_invoice.write(' </Allegati' + newline)

        f_invoice.write('</FatturaElettronicaBody' + newline)
        f_invoice.write('</p:FatturaElettronica' + newline)

        f_invoice.close()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
