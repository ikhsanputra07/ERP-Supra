import time

from openerp.osv import fields, osv
from openerp import netsvc
from openerp import pooler
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _

class invoice_multi_po(osv.osv_memory):
	_name = "invoice.multi.po"
	_description = "Invoice Multi PO"

	def fields_view_get(self, cr, uid, view_id=None, view_type='form',
						context=None, toolbar=False, submenu=False):
		if context is None:
			context={}
		
		if context.get('active_model','') == 'purchase.order' and len(context['active_ids']) < 2:
			raise osv.except_osv(_('Warning!'),
			_('Please select multiple order to merge in the list view.'))
		else:
			
			if context.get('active_model','') == 'purchase.order' and len(context['active_ids']) > 1:
				partner = []
				pricelist = []
				for x in context['active_ids']:
					data =self.pool.get('purchase.order').browse(cr,uid,x)

					partner+=[data.partner_id.id]
					pricelist+=[data.pricelist_id.id]

				cekpartner  = []
				for val in partner:
					if val == partner[0]:
						cekpartner += [val]

				cekpricelist  = []
				for val_pricelist in pricelist:
					if val_pricelist == pricelist[0]:
						cekpricelist += [val_pricelist]

				# Cek Partner Harus Sama
				if len(context['active_ids']) <> len(cekpartner):
					raise osv.except_osv(_('Warning!'),
					_('Invoice tidak dapat dibuat untuk beberapa supplier'))
				
				# Cek Pricelist Harus Sama
				if len(context['active_ids']) <> len(cekpricelist):
					raise osv.except_osv(_('Warning!'),
					_('Invoice tidak dapat dibuat untuk beberapa Pricelist'))
				
				# Cek Validasi PO Apakah sudah memiliki Invoice
				for z in context['active_ids']:
					cr.execute("SELECT invoice_id FROM purchase_invoice_rel WHERE purchase_id = %s", [x])
					invoice = map(lambda x: x[0], cr.fetchall())

					inv =self.pool.get('purchase.order').browse(cr,uid,z)
					data_invoice =self.pool.get('account.invoice').browse(cr,uid,invoice)

					no_kwitansi = ''
					for c in data_invoice:
						no_kwitansi += c.kwitansi + ', '

					if invoice:
						raise osv.except_osv(_('Warning!'),
						_('Purchase Order ' + inv.name + ' Sudah Memiliki Invoice ' + no_kwitansi))		

					

		return super(invoice_multi_po, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
	
	def merge_orders_invoice(self, cr, uid, ids, context=None):
		fiscal_position_id=False
		order_obj = self.pool.get('purchase.order')
		accinv_obj = self.pool.get('account.invoice')
		accinv_line_obj = self.pool.get('account.invoice.line')
		invoice_rel = self.pool.get('purchase.invoice.rel')
		account_tax = self.pool.get('account.tax')
		account_fiscal_position = self.pool.get('account.fiscal.position')
		if context is None:
			context = {}

		partner = []
		currency_id = []
		amount_untaxed = 0
		amount_tax = 0
		amount_total =0 
		no_po = ''

		line_id = []
		tax_id = []

		for x in context['active_ids']:
			data =self.pool.get('purchase.order').browse(cr,uid,x)
			no_po += data.name + ', '
			partner+=[data.partner_id.id]
			amount_untaxed += data.amount_untaxed
			amount_tax += data.amount_tax
			amount_total += data.amount_total
			currency_id += [data.pricelist_id.id]

			for line in data.order_line:
				line_id += [line.id]
				tax_id += [line.product_id.supplier_taxes_id]
		
		line = self.pool.get('purchase.order.line').browse(cr,uid,line_id[0])	
		
		data_partner= self.pool.get('res.partner').browse(cr,uid,partner[0])
		currency =self.pool.get('product.pricelist').browse(cr,uid, currency_id[0])

		desc = 'Merge PO Dalam 1 Invoice ' + data_partner.name + ' Dengan No PO ' + no_po
		
		sid = accinv_obj.create(cr, uid, {
								'account_id': 119,
								'company_id':1,
								'currency_id':currency.currency_id.id,
								'partner_id':partner[0],
								'user_id':uid,
								'reference_type':'none',
								'journal_id':2,
								'amount_tax':amount_tax,
								'state':'draft',
								'type':'in_invoice',
								'date_invoice':time.strftime("%Y-%m-%d"),
								'amount_untaxed':amount_untaxed,
								'name':desc,
								'sent':False,
								'commercial_partner_id':partner[0],
								'faktur_pajak_no':'0000000000000000'
							   })

		taxes = account_tax.browse(cr, uid, map(lambda line: line.id,line.product_id.supplier_taxes_id))
		fpos = fiscal_position_id and account_fiscal_position.browse(cr, uid, fiscal_position_id, context=context) or False
		taxes_ids = account_fiscal_position.map_tax(cr, uid, fpos, taxes)
		accinv_line_obj.create(cr, uid, {
								 'origin':desc,
								 'uos_id':1,
								 'account_id':46,
								 'name':desc,
								 'sequence':10,
								 'invoice_id':sid,
								 'price_unit':amount_untaxed,
								 'price_subtotal':amount_untaxed,
								 'company_id':1,
								 'discount':0.00,
								 'quantity':1.00,
								 'partner_id':partner[0],
								 'invoice_line_tax_id': [(6,0,taxes_ids)],
								 })

		# Daftarkan Ke Purchase Invoice Rel
		for y in context['active_ids']:
			cr.execute('insert into purchase_invoice_rel (purchase_id,invoice_id) values (%s,%s)', (y, sid))

		pool_data=self.pool.get("ir.model.data")
		action_model,action_id = pool_data.get_object_reference(cr, uid, 'account', "invoice_supplier_form")     
		action_pool = self.pool.get(action_model)
		res_id = action_model and action_id or False
		action = action_pool.read(cr, uid, action_id, context=context)
		action['name'] = 'account.invoice.supplier.form'
		action['view_type'] = 'form'
		action['view_mode'] = 'form'
		action['view_id'] = [res_id]
		action['res_model'] = 'account.invoice'
		action['type'] = 'ir.actions.act_window'
		action['target'] = 'current'
		action['res_id'] = sid
		return action

invoice_multi_po()


class purchase_order(osv.osv):
	_inherit = 'purchase.order'

	def action_invoice_create(self, cr, uid, ids, context=None):
		cr.execute("SELECT invoice_id FROM purchase_invoice_rel WHERE purchase_id = %s", ids)
		invoice = map(lambda x: x[0], cr.fetchall())

		data_invoice =self.pool.get('account.invoice').browse(cr,uid,invoice)
		no_kwitansi = ''
		for c in data_invoice:
			if c.kwitansi:
				no_kwitansi += c.kwitansi + ', '

		if invoice:
			raise osv.except_osv(_('Warning!'),
			_('Purchase Order Sudah Memiliki Invoice ' + no_kwitansi))

		return super(purchase_order,self).action_invoice_create(cr,uid,ids,context=context)

class purchase_partial_invoice(osv.osv_memory):
	_inherit = "purchase.partial.invoice"
	

	def create_invoices(self, cr, uid, ids, context=None):
		val = self.browse(cr, uid, ids)[0]

		purchase_ids = context.get('active_ids', [])
		# Cek Total di PO 
		po =self.pool.get('purchase.order').browse(cr,uid,purchase_ids)[0]
		total_po = po.amount_total

		# Akumulasi Nilai Yang diminta dengan yang sudah di buat Invoice
		cek_total = (total_po * val.amount) / 100

		cr.execute("SELECT invoice_id FROM purchase_invoice_rel WHERE purchase_id = %s", purchase_ids)
		invoice = map(lambda x: x[0], cr.fetchall())

		if invoice:		
			total_invoice = 0
			for x in invoice:
				inv =self.pool.get('account.invoice').browse(cr,uid,x)
				total_invoice += inv.amount_total

			akumulasi_total = total_invoice + cek_total
			if total_invoice == total_po:
				raise osv.except_osv(_('Warning!'),
				_('Purchase Order Sudah Tidak Bisa Dibuat Invoice'))
			elif akumulasi_total > total_po:
				raise osv.except_osv(_('Warning!'),
				_('Nilai Persentase yang Anda Input Terlalu Besar, Total Invoice Sudah Melebih Nilai PO '))

		return super(purchase_partial_invoice,self).create_invoices(cr,uid,ids,context=context)