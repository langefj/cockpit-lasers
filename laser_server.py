import serial
import socket
import threading
import time
import Pyro4

CONFIG_NAME = 'laserServer'

class Server(object):
    def __init__(self):
        self.run_flag = True
        self.threads = []
        self.daemons = []
        self.devices = {}


    def run(self):
        import readconfig
        config = readconfig.config
        try:
            supported_lasers = config.get(CONFIG_NAME, 'supported').split(' ')
        except:
            raise Exception('No supported laser modules defined in config.')

        loaded_modules = {}
        for module in supported_lasers:
            try:
                m = __import__(module)
            except:
                raise Exception("Could not load module %s." % module)
            loaded_modules.update({module: m})

        lasers = {section: module_name
                    for section in config.sections() 
                    for module_name in supported_lasers
                    if section.startswith(module_name)}

        # Create laser instances and map to Pyro names
        for section, module_name in lasers.iteritems():
            com = config.get(section, 'comPort')
            baud = config.get(section, 'baud')
            try:
                timeout = config.get(section, 'timeout')
            except:
                timeout = 1.
            # Create an instance of the laser m.CLASS_NAME in module m.
            m = loaded_modules[module]
            laser_instance = getattr(m, m.CLASS_NAME)(com, int(baud), int(timeout))
            
            # Add this to the dict mapping lasers to Pyro names.
            self.devices.update({laser_instance: section})


        port = config.get(CONFIG_NAME, 'port')
        host = config.get(CONFIG_NAME, 'ipAddress')

        daemon = Pyro4.Daemon(port=int(port), host=host)
        # Start the daemon in a new thread.
        daemon_thread = threading.Thread(
            target=Pyro4.Daemon.serveSimple,
            args = (self.devices, ), # our mapping of class instances to names
            kwargs = {'daemon': daemon, 'ns': False}
            )
        daemon_thread.start()

        self.daemons.append(daemon)
        self.threads.append(daemon_thread)


        # Wait until run_flag is set to False.
        while self.run_flag:
            time.sleep(1)

        # Do any cleanup.
        for daemon in self.daemons():
            daemon.Shutdown()

        for (device, name) in self.devices():
            device.disable()
            del(device)

        for thread in self.threads():
            thread.stop()
            thread.join()


    def shutdown(self):
        self.run_flag = 0