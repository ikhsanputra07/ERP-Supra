# -*- encoding: utf-8 -*-
import time
from osv import fields, osv
from tools.translate import _

class account_invoice(osv.osv):

	_inherit = "account.invoice"
	_columns = {
		'picking_ids': fields.one2many('stock.picking','invoice_id', 'Delivery Orders'),
	}
	
account_invoice()

class stock_picking(osv.osv):

	_inherit = "stock.picking"
	_columns = {
		'invoice_id': fields.many2one('account.invoice','Invoice')
	}
	
stock_picking()

	
class merge_pickings(osv.osv_memory):
	_name = "merge.pickings"
	_columns = {
		'partner_id': fields.many2one('res.partner','Partner', required=True),
		'type': fields.selection([('out', 'Customer Invoice (AR)'), ('in', 'Supplier Invoice (AP)')], 'Type', readonly=False, select=True, required=True),
		'picking_ids': fields.many2many('stock.picking','merge_do_picking_rel','merge_do_id','picking_id','Pickings', required=True, domain="[('state', '=', 'done'), ('type', '=', type), ('partner_id', '=', partner_id)]"),
	}
	
	_defaults = {'type' : 'in'}
	
	def partner_id_change(self, cr, uid, ids):
		return {'value':{'picking_ids': None}}
	
	def type_change(self, cr, uid, ids, tipe):
		domain = {'partner_id': [('customer', '=', True)]}
		if tipe == 'in':
			domain = {'partner_id': [('supplier', '=', True)]}
		return {'value':{'picking_ids':None, 'partner_id': None}, 'domain': domain}
				
	def merge_orders(self, cr, uid, ids, context={}):
		pool_data = self.pool.get('ir.model.data')
		journal_obj = self.pool.get('account.journal')
		pool_invoice = self.pool.get('account.invoice')
		pool_picking = self.pool.get('stock.picking')
		pool_partner = self.pool.get('res.partner')
		pool_invoice_line = self.pool.get('account.invoice.line')
		
		data = self.browse(cr, uid, ids, context=context)[0]
		picking_ids = [x.id for x in data['picking_ids']]
		partner_obj = data['partner_id']
		
		alamat = pool_partner.address_get(cr, uid, [partner_obj.id],['contact', 'invoice'])
		address_contact_id = alamat['contact']
		address_invoice_id = alamat['invoice']
			   
		picking = pool_picking.browse(cr, uid, picking_ids[0], context=context)
		namepick = False
		origin = False
		if data.type == 'out':
			type_inv = 'out_invoice'
			account_id = partner_obj.property_account_receivable.id
			curency = picking.sale_id.pricelist_id.currency_id.id
			journal_ids = journal_obj.search(cr, uid, [('type','=','sale'),('company_id', '=', 1)], limit=1)


			origin = ''
			namepick = ''
			for picking in pool_picking.browse(cr, uid, picking_ids, context=context):
				if picking.note_id.id:
					origin += picking.origin +':'+ (picking.note_id.name)[:7] + ', '
				else:
					origin += picking.origin+ ', '

				namepick += picking.sale_id.client_order_ref + ', '

		elif data.type == 'in':
			type_inv = 'in_invoice'
			account_id = partner_obj.property_account_payable.id
			curency = picking.purchase_id.pricelist_id.currency_id.id
			journal_ids = journal_obj.search(cr, uid, [('type','=','purchase'),('company_id', '=', 1)], limit=1)
		
		if not journal_ids:
			raise osv.except_osv(('Error !'), ('There is no sale/purchase journal defined for this company'))            


		user = self.pool.get('res.users').browse(cr,uid,uid,context=context)

		if curency != user.company_id.currency_id.id:
			cr.execute('SELECT "rating" FROM "res_currency_rate" WHERE "currency_id" = %s ORDER BY "name" DESC limit 1',(curency,))
			today_rate = cr.fetchone()[0]
		else:
			today_rate = 1.0

		invoice_id = pool_invoice.create(cr, uid, {
			'name': namepick[:-2] if namepick else 'Merged Invoice for '+ partner_obj.name + ' on ' + time.strftime('%Y-%m-%d %H:%M:%S'),
			# 'name': 'Merged Invoice for '+ partner_obj.name + ' on ' + time.strftime('%Y-%m-%d %H:%M:%S'),
			'type': type_inv,
			'account_id': account_id,
			'partner_id': partner_obj.id,
			'journal_id': journal_ids[0] or False,
			'address_invoice_id': address_invoice_id,
			'address_contact_id': address_contact_id,
			'date_invoice': time.strftime('%Y-%m-%d'),
			'user_id': uid,
			'origin':origin[:-2] if origin else False,
			'currency_id': curency or False,
			'picking_ids': [(6,0, picking_ids)],
			'pajak': today_rate,
		})

		batched_product = {}
		batched_qty_total = {}			 
		for picking in pool_picking.browse(cr, uid, picking_ids, context=context):
			pool_picking.write(cr, uid, [picking.id], {'invoice_state': 'invoiced', 'invoice_id': invoice_id}) 
			for move_line in picking.move_lines:
				disc_amount = 0
				if data.type == 'out':
					price_unit = pool_picking._get_price_unit_invoice(cr, uid, move_line, 'out_invoice')
					tax_ids = pool_picking._get_taxes_invoice(cr, uid, move_line, 'out_invoice')
					line_account_id = move_line.product_id.product_tmpl_id.property_account_income.id or move_line.product_id.categ_id.property_account_income_categ.id
				elif data.type == 'in':
					price_unit = pool_picking._get_price_unit_invoice(cr, uid, move_line, 'in_invoice')
					tax_ids = pool_picking._get_taxes_invoice(cr, uid, move_line, 'in_invoice')
					line_account_id = move_line.product_id.product_tmpl_id.property_account_expense.id or move_line.product_id.categ_id.property_account_expense_categ.id
					disc_amount = move_line.purchase_line_id.discount_nominal
				discount = pool_picking._get_discount_invoice(cr, uid, move_line)
				 
				origin = picking.origin +':'+ (picking.name).strip()
				#origin = (picking.delivery_note).strip() +';'+ (picking.name).strip()

				if move_line.product_id.track_incoming or move_line.product_id.track_outgoing:
					if not batched_product.get(move_line.sale_line_id.id):
						batched_product.update({move_line.sale_line_id.id:{}})
						

					if not batched_qty_total.get(move_line.sale_line_id.id):
						batched_qty_total[move_line.sale_line_id.id] = 0

					batched_qty_total[move_line.sale_line_id.id] += move_line.product_qty

					_logger.error('roductttttt -----------%s',move_line.product_id.name_template)

					if not batched_product.get(move_line.sale_line_id.id):
						_logger.error('no exist get----------------------------------------------------------- %s',move_line.sale_line_id.id)
						batched_product.update({move_line.sale_line_id.id:{}})

					batched_product[move_line.sale_line_id.id].update({
						'name': "["+move_line.product_id.default_code+"] "+move_line.product_id.name_template,
						'invoice_id': invoice_id,
						'picking_id': picking.id,

						'product_id':move_line.product_id.id,
						'quantity':batched_qty_total[move_line.sale_line_id.id],

						'origin': origin,
						'uos_id': move_line.product_uos.id or move_line.product_uom.id,
						'price_unit': price_unit,
						'discount': discount,
						'invoice_line_tax_id': [(6, 0, tax_ids)],
						'account_analytic_id': pool_picking._get_account_analytic_invoice(cr, uid, picking, move_line),
						'account_id': self.pool.get('account.fiscal.position').map_account(cr, uid, partner_obj.property_account_position, line_account_id),
						'amount_discount':disc_amount

					})

					_logger.error('Batched Product to be %s',batched_product)
					continue; #next loop for canceling creating invoice line
				if picking.note_id:
					# search op line id by move line ID
					
					cekopline=self.pool.get('order.preparation.line').search(cr,uid,[('move_id', '=' ,move_line.id)])

					op_line=self.pool.get('order.preparation.line').browse(cr,uid,cekopline)
					
					if op_line:
						for opl in op_line:
							#Search DN Line ID By OP Line ID
							cek=self.pool.get('delivery.note.line').search(cr,uid,[('op_line_id', '=' ,opl.id)])
							product_dn=self.pool.get('delivery.note.line').browse(cr,uid,cek)[0]

							if cek:
								pool_invoice_line.create(
									cr, uid, 
									{
										'name': product_dn.name,
										'picking_id': picking.id,
										'origin': origin,
										'uos_id': move_line.product_uos.id or move_line.product_uom.id,
										'product_id': move_line.product_id.id,
										'price_unit': price_unit,
										'discount': discount,
										'quantity': move_line.product_qty,
										'invoice_id': invoice_id,
										'invoice_line_tax_id': [(6, 0, tax_ids)],
										'account_analytic_id': pool_picking._get_account_analytic_invoice(cr, uid, picking, move_line),
										'account_id': self.pool.get('account.fiscal.position').map_account(cr, uid, partner_obj.property_account_position, line_account_id),
										'amount_discount':disc_amount
									}
								)
							else:
								raise osv.except_osv(('Perhatian..!!'), ('No Delivery Note Tidak Ditemukan'))
						# end for
					else:
						if picking.note_id:
							if move_line.name:
								name_inv_line = move_line.name
							elif move_line.desc:
								name_inv_line = move_line.desc
							else:
								name_inv_line = "["+move_line.product_id.default_code+"] "+move_line.product_id.name_template
						
						pool_invoice_line.create(
							cr, uid, 
							{
								# 'name': picking.origin +':'+ (picking.name).strip(), #move_line.name,
								'name': name_inv_line,
								'picking_id': picking.id,
								'origin': origin,
								'uos_id': move_line.product_uos.id or move_line.product_uom.id,
								'product_id': move_line.product_id.id,
								'price_unit': price_unit,
								'discount': discount,
								'quantity': move_line.product_qty,
								'invoice_id': invoice_id,
								'invoice_line_tax_id': [(6, 0, tax_ids)],
								'account_analytic_id': pool_picking._get_account_analytic_invoice(cr, uid, picking, move_line),
								'account_id': self.pool.get('account.fiscal.position').map_account(cr, uid, partner_obj.property_account_position, line_account_id),
								'amount_discount':disc_amount
							}
						)
				else:
					pool_invoice_line.create(
						cr, uid, 
						{
							# 'name': picking.origin +':'+ (picking.name).strip(), #move_line.name,
							'name': move_line.name,
							'picking_id': picking.id,
							'origin': origin,
							'uos_id': move_line.product_uos.id or move_line.product_uom.id,
							'product_id': move_line.product_id.id,
							'price_unit': price_unit,
							'discount': discount,
							'quantity': move_line.product_qty,
							'invoice_id': invoice_id,
							'invoice_line_tax_id': [(6, 0, tax_ids)],
							'account_analytic_id': pool_picking._get_account_analytic_invoice(cr, uid, picking, move_line),
							'account_id': self.pool.get('account.fiscal.position').map_account(cr, uid, partner_obj.property_account_position, line_account_id),
							'amount_discount':disc_amount
						}
					)
		if batched_product:
			for batch in batched_product:
				_logger.error('BATTTTTTTTTTTTTT >>>>>>>>>>>>>>>>>>>>>>>>>>>>%s',batch)
				invline_id = pool_invoice_line.create(cr,uid,batched_product[batch])
				
		pool_invoice.button_compute(cr, uid, [invoice_id], context=context, set_total=False)           
		action_model,action_id = pool_data.get_object_reference(cr, uid, 'account', "invoice_form")
		if data.type == 'in':
			action_model,action_id = pool_data.get_object_reference(cr, uid, 'account', "invoice_supplier_form")
		 
		action_pool = self.pool.get(action_model)
		res_id = action_model and action_id or False
		action = action_pool.read(cr, uid, action_id, context=context)
		action['name'] = 'Merged Invoice'
		action['view_type'] = 'form'
		action['view_mode'] = 'form'
		action['view_id'] = [res_id]
		action['res_model'] = 'account.invoice'
		action['type'] = 'ir.actions.act_window'
		action['target'] = 'current'
		action['res_id'] = invoice_id
		return action
	
merge_pickings()