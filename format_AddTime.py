from datetime import datetime, timedelta
import logging

# Helper Function to add a time and Minues together
# "{AddTime:13:15?45}".format(AddTime=AddTime())
class AddTime(object):
    def __format__(self, add_time):
        try:
            values = add_time.split('?')
            if len(values) == 2: 
                input_time = datetime.strptime(values[0], "%H:%M") + timedelta(minutes=int(values[1]))
                return datetime.strftime(input_time, "%H:%M")
        except Exception as e:
            logging.error("Unable to add time togeather: {}".format(add_time))
        return ""
