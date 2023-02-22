from threading import Thread,Event
from PyQt6.QtCore import QThread
from PyQt6 import QtCore
import socket
import logging
from typing import Callable
from modbus_poll import modbus_poll

class rotem_thread(Thread):
    def __init__(self,sock:socket.socket=None,callback=None,tick=0.3,log:logging=None,exit:Event=None, address:str = None):
        super(rotem_thread,self).__init__(None)
        
        self.log = log

        if sock is None:
            raise Exception("get status thread require 'socket")
        if sock.fileno() == -1:
            raise Exception("socket is closed")
        self._sock = sock
        self._stop = Event()
        self._callback = callback
        self._tick = tick
        self.queue = []
        self.exit = exit
        self._modbus = modbus_poll(host = address, exit = exit, log = log)
        self._modbus_callback = None
        self._loss = None

    def stop(self):
        self._stop.set()
        self._modbus._stop.set()

    def stopped(self):
        return self._stop.is_set()

    def command(self,cmd:str=None,callback=None):
        if cmd is not None:
            cmd = cmd + "\r\n"
        self.queue.append({
            'cmd':cmd.encode('utf-8') if cmd is not None else None,
            'call':callback
        })

    @property
    def modbus(self):
        return self._modbus.callback
    
    @modbus.setter
    def modbus(self,val):
        self._modbus.callback = val
    
    @property
    def loss(self):
        return self._loss
    
    @loss.setter
    def loss(self,val):
        self._loss = val

    def run(self):
        sock = self._sock
        while not self._stop.is_set() and not self.exit.is_set():
            try:
                if len(self.queue) == 0:
                    sock.send(b"status\r\n")
                    recv = sock.recv(1024)
                    if recv is None:
                        self._stop.set()
                        break
                    recv = recv.decode().strip()
                    if (recv.count(',') == 3):
                        if self._callback is not None:
                            self._callback(recv)
                        ready_state,_,_,_ = recv.split(',')
                        if ready_state != 0 and ready_state == 4 and not self._modbus.running():
                            self._modbus.start()
                    self._stop.wait(timeout=self._tick)
                else:
                    excute = self.queue.pop()
                    self.log.debug(f'{excute["cmd"]}')
                    if excute['cmd'] is not None:
                        sock.send(excute['cmd'])
                    recv = sock.recv(1024)
                    if recv is None:
                        self._stop.set()
                        break
                    recv = recv.decode().strip()
                    # self.log.debug(f'{recv}')
                    if excute['call'] is not None:
                        if type(excute['call']) is str:
                            self.log.debug(excute['call'])
                        else:
                            excute['call'](recv)
            except Exception as ex:
                self._stop.set()
                self._modbus._stop.set()
                self.log.error(ex)
                break
        try:
            self._stop.set()
            self._modbus._stop.set()
            self.log.debug("Bye")
            sock.close()
        except:pass
        if self._loss is not None:
            self._loss()