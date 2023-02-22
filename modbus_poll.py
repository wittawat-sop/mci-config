from threading import Thread,Event
from PyQt6.QtCore import QThread
from pyModbusTCP.client import ModbusClient
import logging
class modbus_poll(Thread):
    def __init__(self,host:str='192.168.1.101',port:int=502,tick:float=1,callback=None,log:logging=None,exit:Event=None):
        super(modbus_poll,self).__init__(None)
        self._callback = callback
        self._client = ModbusClient(host,port,1,1,auto_open=True,debug=False)
        self._stop = Event()
        self._tick = tick
        self.log = log
        self.exit = exit
        self._run = False

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.is_set()
    
    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self,val):
        self._callback = val

    def running(self):
        return self._run

    def run(self):
        self._run = True
        while not self._stop.is_set() and not self.exit.is_set():
            reg = self._client.read_input_registers(0,0x18)
            if self._callback is not None:
                self._callback(reg)
            self._stop.wait(self._tick)
        try:
            self._client.close()
            self.log.debug("Bye")
        except:pass

if __name__ == "__main__":
    def recv(data):
        print(data)
    import time
    test = modbus_poll(callback=recv)
    time.sleep(0.5)
    test.start()
    time.sleep(5)
    test.stop()
