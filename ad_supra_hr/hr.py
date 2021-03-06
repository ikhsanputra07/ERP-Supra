import time
import calendar
from osv import fields, osv

class regional(osv.osv):
    _name = "regional"
    
    _columns = {
            'name' : fields.char("Regional Name", size=200,required=True),
	    'description' : fields.text("Description"),
    }

class hr_employee(osv.osv):
    _inherit = "hr.employee"
    _columns = {
	'regional' : fields.many2one('regional','Regional',reqired=True),
    'psm' : fields.char('PSM',size=64,reqired=True),
    }

