import random
import string

BROWSER_WIDTH = 1300
BROWSER_HEIGHT = 600

NON_TEXT_INPUT_TYPES = ['checkbox', 'radio']
LINK_INPUT_TYPES = ['a']

EMAIL_INPUT = 'vsbharadwaj.machiraju.ece12+%d@iitbhu.ac.in' % (random.randint(0, 1000))
MOBILE_INPUT = '+919956448732'
ZIPCODE_INPUT = '56003'
ADDRESS_INPUT = 'Australia'
DATE_INPUT = '25/12/1993'
TEXT_INPUT = ''.join([random.choice(list(string.lowercase)) for i in range(0, 7)])
PASSWORD_INPUT = ''.join([random.choice(list(string.lowercase)) for i in range(0, 3)]) + random.choice(list(string.uppercase)) + '7!'


STATE_D2V_DIM = 3
STATE_FORM_N = 2
STATE_LINK_N = 12
