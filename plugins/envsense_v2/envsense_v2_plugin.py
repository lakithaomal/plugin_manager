# -*- coding: utf-8 -*-
import logging
import coresense


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class register(object):

    def __init__(self, name, man, mailbox_outgoing):
        
        env = envsense(name, man, mailbox_outgoing)
        
        env.run()
    


class envsense(object):

    plugin_name = 'envsense'
    plugin_version = '2'

    def __init__(self, name, man, mailbox_outgoing):
        self.name = name
        self.man = man
        self.outqueue = mailbox_outgoing
        

    def run(self):
        with coresense.create_connection('/dev/ttyACM0') as conn:
            self.running = True
            while self.running:
                
                try:
                    msg = conn.recv()
                except Exception as e:
                    logger.error("Error of type %s: %s" % (str(type(e)), str(e)))
                    msg = None
                    
                if msg:    
                    self.handle_message()

    def stop(self):
        self.running = False

    def handle_message(self, message):
        logger.info(message)
        for entry in message.entries:
            self.handle_message_entry(message, entry)

    def handle_message_entry(self, message, entry):
        self.outqueue.put([
            str(message.timestamp.date()),
            self.plugin_name,
            self.plugin_version,
            'default',
            str(message.timestamp),
            entry.sensor,
            'meta.txt',
            format_entry_values(entry),
        ])

    @property
    def running(self):
        return self.man[self.name] != 0

    @running.setter
    def running(self, state):
        self.man[self.name] = 1 if state else 0



def format_entry_values(entry):
    return ['{}:{}'.format(key, value) for key, value in entry.values]
