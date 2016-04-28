import random
import string

BROWSER_WIDTH = 1300
BROWSER_HEIGHT = 600

NON_TEXT_INPUT_TYPES = ['checkbox', 'radio']

EMAIL_INPUT = 'vsbharadwaj.machiraju.ece12@iitbhu.ac.in'
MOBILE_INPUT = '+919956448732'
ZIPCODE_INPUT = '56003'
ADDRESS_INPUT = 'Australia'
TEXT_INPUT = ''.join([random.choice(list(string.lowercase)) for i in range(0, 7)])
PASSWORD_INPUT = ''.join([random.choice(list(string.lowercase)) for i in range(0, 7)])
