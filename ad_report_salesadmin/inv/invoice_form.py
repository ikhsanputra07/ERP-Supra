import time
from report import report_sxw
from osv import osv,fields
from report.render import render
from ad_num2word_id import num2word
import pooler
#from report_tools import pdf_fill,pdf_merge
from tools.translate import _
import tools
from tools.translate import _
import decimal_precision as dp
#from ad_amount2text_idr import amount_to_text_id
from tools import amount_to_text_en 


class invoice_form(report_sxw.rml_parse):
    
    def __init__(self, cr, uid, name, context):
        super(invoice_form, self).__init__(cr, uid, name, context=context)
        #if self.pool.get('sale.order').browse(cr, uid, context['active_ids'])[0].state <> 'approved':
        #    raise osv.except_osv(_('Can not Print PO Form !'), _('You can not Print PO Form If State not Approved'))
#        
       # self.line_no = 0
        self.localcontext.update({
            'get_object':self._get_object,
#            'time': time,
            'convert':self.convert,
#            'get_company_address': self._get_company_address,
#            #'angka':self.angka,
##            'alamat': self.alamat_npwp,
#            'convert':self.convert,
#            'charge':self.charge,
##            'nourut': self.no_urut,
##            'get_ppn': self.get_ppn,
#            'line_no':self._line_no,
#            'blank_line':self.blank_line,
#            'blank_line_rfq':self.blank_line_rfq,
#            'get_grand_total':self.get_grand_total,
#            'get_internal':self._get_internal,
#            'sum_tax':self._sum_tax,
#            'get_curr2':self.get_curr,
#            'get_invoice':self._get_invoice,
#            'get_curr':self._get_used_currency,
        }) 
        
    def _get_object(self,data):
        obj_data=self.pool.get(data['model']).browse(self.cr,self.uid,[data['id']])
#        seq=obj_data[0].print_seq
#        seq+=1
#        obj_data[0].write({'print_seq':seq})
        return obj_data
   
    def convert(self, amount_total, cur):
        #amt_id = amount_to_text_id.amount_to_text(amount_total, 'id', cur)
        amt_id = num2word.num2word_id(amount_total,"id").decode('utf-8')
        return amt_id

report_sxw.report_sxw('report.invoice2.form', 'account.invoice', 'ad_report_salesadmin/inv/invoice_form.mako', parser=invoice_form,header=False)
