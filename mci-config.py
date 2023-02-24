import time
import logging
import sys
import socket

from rotem_thread import rotem_thread
from modbus_poll import modbus_poll
from rotem_comm_state import rotem_comm_state
from PyQt6.QtWidgets import QMainWindow,QApplication,QTableWidgetItem,QHeaderView,QFileDialog
from PyQt6 import QtGui,QtCore

from threading import Event
from main_ui import Ui_MainWindow

class MainWidows(QMainWindow,Ui_MainWindow):
    statusMessage = QtCore.pyqtSignal(str)
    def __init__(self,*args,obj=None,**kwargs):
        super(MainWidows,self).__init__(*args,**kwargs)
        
        log_stream = logging.StreamHandler()
        log_stream.setFormatter(logging.Formatter('%(module)15s %(levelname)s - %(funcName)20s - %(lineno)4d - %(message)s '))
        log_stream.setLevel(logging.DEBUG)
        self.log = logging.getLogger("MC-Intellisense")
        self.log.setLevel(logging.DEBUG)
        self.log.addHandler(log_stream)

        self.setupUi(self)
        self._rotem_thread = None
        self.stop = Event()
        self.address = ""

        self.btn_find_device.clicked.connect(self.find_device)
        self.list_device.doubleClicked.connect(self.modbus_connect)
        self.btn_refresh.clicked.connect(self.list_ethernet_device)
        self.btn_connect.clicked.connect(self.modbus_connect)
        self.btn_disconnect.clicked.connect(self.disconnect)
        self.btn_get_config.clicked.connect(lambda : self._rotem_thread.command("info",self.update_device_info))
        self.btn_fw_upgrade.clicked.connect(self.firmware_upgrade)
        self.btn_set_config.clicked.connect(self.set_device_info)
        self.cb_dhcp_ip.stateChanged.connect(self.dhcp_enable)
        self.btn_random_mac.clicked.connect(self.random_mac_address)
        self.disable_config()

        self.rotem_status_tabel.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.rotem_status_tabel.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.rotem_status_tabel.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        self.statusMessage.connect(self.statusbarHandle)

        self._register_table=[
            {'row':0,'Address':'0000','Description':'status','multiply':1},
            {'row':1,'Address':'0001','Description':'barn','multiply':1},
            {'row':2,'Address':'0002','Description':'machine version','multiply':1},
            {'row':3,'Address':'0003','Description':'vent level','multiply':1},
            {'row':4,'Address':'0004','Description':'heater status','multiply':1},

            {'row':5,'Address':'0005','Description':'cooling status','multiply':1},
            {'row':6,'Address':'0006','Description':'fogger status','multiply':1},
            {'row':7,'Address':'0007','Description':'grow day','multiply':1},
            {'row':8,'Address':'0008','Description':'pressure','multiply':0.0001},
            {'row':9,'Address':'0009','Description':'pressure.sp','multiply':0.0001},

            {'row':10,'Address':'000A','Description':'temp.inside','multiply':0.01},
            {'row':11,'Address':'000B','Description':'temp.sp','multiply':0.01},
            {'row':12,'Address':'000C','Description':'heater.sp','multiply':0.01},
            {'row':13,'Address':'000D','Description':'cooling.sp','multiply':0.01},
            {'row':14,'Address':'000E','Description':'humi.inside','multiply':0.01},

            {'row':15,'Address':'000F','Description':'humi.outside','multiply':0.01},
            {'row':16,'Address':'0010','Description':'humi.sp','multiply':0.01},
            {'row':17,'Address':'0011','Description':'daily feed','multiply':1},
            {'row':18,'Address':'0012','Description':'daily water','multiply':1},
            {'row':19,'Address':'0013','Description':'alarm code[0]','multiply':1},

            {'row':20,'Address':'0014','Description':'alarm code[1]','multiply':1},
            {'row':21,'Address':'0015','Description':'alarm code[2]','multiply':1},
            {'row':22,'Address':'0016','Description':'alarm code[3]','multiply':1},
            {'row':23,'Address':'0017','Description':'alarm code[4]','multiply':1},
            ]
   
    def statusbarHandle(self,msg):
        # self.log.debug(msg)
        self.status_bar.showMessage(msg)
        QtCore.QCoreApplication.processEvents()

    def firmware_begin_update(self):
        time.sleep(3)
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.settimeout(10)
        try:
            sock.connect((self.address,50002))
            self.log.debug(f'{sock.recv(1024).decode().strip()}')
            uploaded_size = 0
            i = 0
            # self.status_bar.showMessage(f'Uploaded... 0%')
            self.statusMessage.emit(f'Uploaded... 0%')
            with open(self.fw_file,'rb') as fp:
                while True:
                    dat = fp.read(1024)
                    if len(dat) == 0:
                        break
                    i += 1
                    # self.log.debug(f'read file {(len(dat)/1024) if len(dat) >=1024 else len(dat) }{" kB" if len(dat)>1023 else " Bytes"} [{i}]')
                    sock.send(dat)
                    recv = sock.recv(1024)
                    if recv is None:break
                    if len (recv) == 2:
                        # self.log.debug(f'writed :{(256*recv[0]+recv[1])}Bytes')
                        uploaded_size += (256*recv[0]+recv[1])
                        # self.data_monitoring.appendPlainText(f'Uploaded... {int(uploaded_size/self.file_size)}%')
                        self.statusMessage.emit(f'Uploaded... {int(100*uploaded_size/self.file_size)}%')
                        time.sleep(0.1)
            time.sleep(1)
            # self.log.debug(f'Uploaded file remain : {self.file_size - uploaded_size} Bytes')
            if self.file_size - uploaded_size == 0:
                # self.status_bar.showMessage('Upload firmware complete...',5000)
                self.statusMessage.emit('Upload firmware complete...')
            else:
                # self.status_bar.showMessage(f'Upload fail!...[remain : {self.file_size - uploaded_size}-byte]')
                self.statusMessage.emit(f'Upload fail!...[remain : {self.file_size - uploaded_size}-byte]')
            self.disconnect()
        except Exception as ex:
            # self.status_bar.showMessage(f'Upload fail!...[Exception]')
            self.statusMessage.emit(f'Upload fail!...[Exception]')
            self.log.debug(ex)
        self.disconnect()
        time.sleep(3)
        self.find_device()
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def firmware_upgrade(self):
        fname,_ = QFileDialog.getOpenFileName(self,"Firmwre file open",'', 'Binary Files (*.bin);;All Files (*)')
        if fname: 
            self.setCursor(QtCore.Qt.CursorShape.WaitCursor)
            self.log.debug(f'Firmware file: {fname}')
            i = 0
            self.statusMessage.emit(f'Loadding file fname')
            with open(fname,'rb') as fp:
                import os
                file_size = os.fstat(fp.fileno()).st_size
                self.log.debug(f'Firmware size: {file_size/1024:0.3f}kB')
                self.statusMessage.emit(f'Begin update firmware ({file_size/1024:0.3f}kB)')
                self.fw_file = fname
                self._rotem_thread.command(f'fwup={file_size}',None)
                self.file_size = file_size
                time.sleep(2)
                self.statusMessage.emit(f'Watiing for connect to {self.address}')
                self.firmware_begin_update()
            
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        pass

    def random_mac_address(self):
        from numpy import random
        mac = ''.join([f'{rnd:02x}' for rnd in random.randint(255,size=(2))])
        self.device_mac.setText("00:08:dc:01:"+mac)

    def list_ethernet_device(self):
        import psutil
        # Get a dictionary of NICs and their addresses
        nics = psutil.net_if_addrs()
        self._ip = []
        self._broadcast = []
        self._device = []
        self.cb_interface_dev.clear()
        # Print the NICs and their addresses
        for nic, addresses in nics.items():
            for address in addresses:
                address = [elm for elm in address]
                if address[0] == socket.AF_INET:
                    addr = [int(s) for s in address[1].split('.')]
                    mask = [int(s) for s in address[2].split('.')]
                    for i in range(0,4):
                        addr[i] |= (mask[i] ^ 0xFF)
                    self._ip.append(address[1])
                    self._broadcast.append(f"{addr[0]}.{addr[1]}.{addr[2]}.{addr[3]}")
                    self.cb_interface_dev.addItem(f"{nic} ({address[1]})")
        if len(self._broadcast) > 0 :
            self.cb_interface_dev.addItem("ALL")
            self.cb_interface_dev.setCurrentText("ALL")

    def recv_register(self,data):
        i = 0
        for elm in data:
            val = (elm * self._register_table[i]['multiply'])
            self.rotem_status_tabel.setItem(i,2,QTableWidgetItem(f'{val}'))
            i = i + 1

    def recv_status(self,data:str=None):
        if data is not None:
            ready_state,scanning_barn,scan_state,comm_state = data.split(',')
            if ready_state == '0':
                self.rotem_connect_status.setText("WAIT TO BARN SCAN")
            elif ready_state == '255':
                self.rotem_connect_status.setText("BOOTLOADER MODE")
            elif scan_state != '4':
                self.rotem_connect_status.setText(f"FINDING BARN...{scanning_barn}")
            else:
                self.rotem_connect_status.setText(f"CONNECTED TO BARN : {scanning_barn} [{rotem_comm_state(int(comm_state)).name}]")
        else:
            self.update_device_info(None)

    def dhcp_enable(self,_):
        if not self.cb_dhcp_ip.isChecked():
            self.device_ip.setEnabled(True)
            self.device_gw.setEnabled(True)
            self.device_sn.setEnabled(True)
        else:
            self.device_ip.setEnabled(False)
            self.device_gw.setEnabled(False)
            self.device_sn.setEnabled(False)

    def enable_config(self):
        self.btn_disconnect.setEnabled(True)
        self.btn_set_config.setEnabled(True)
        self.btn_get_config.setEnabled(True)
        self.cb_dhcp_ip.setEnabled(True)

        if not self.cb_dhcp_ip.isChecked():
            self.device_ip.setEnabled(True)
            self.device_gw.setEnabled(True)
            self.device_sn.setEnabled(True)
        else:
            self.device_ip.setEnabled(False)
            self.device_gw.setEnabled(False)
            self.device_sn.setEnabled(False)

        self.device_mac.setEnabled(True)
        self.rotem_bran_no.setEnabled(True)
        self.rotem_baudrate.setEnabled(True)
        self.device_name.setEnabled(True)
        self.btn_fw_upgrade.setEnabled(True)
        self.btn_random_mac.setEnabled(True)

        self.btn_connect.setEnabled(False)
        self.list_device.setEnabled(False)
    
    def disable_config(self):
        self.btn_disconnect.setEnabled(False)
        self.btn_set_config.setEnabled(False)
        self.btn_get_config.setEnabled(False)
        self.cb_dhcp_ip.setEnabled(False)
        self.device_ip.setEnabled(False)
        self.device_gw.setEnabled(False)
        self.device_sn.setEnabled(False)
        self.device_mac.setEnabled(False)
        self.rotem_bran_no.setEnabled(False)
        self.rotem_baudrate.setEnabled(False)
        self.device_name.setEnabled(False)
        self.btn_fw_upgrade.setEnabled(False)
        self.btn_random_mac.setEnabled(False)
        self.btn_connect.setEnabled(True)
        self.list_device.setEnabled(True)

    def disconnect(self):
        if self._rotem_thread is not None and self._rotem_thread.stopped() == False:
            self._rotem_thread.stop()
        else:
            self.update_device_info()
        self.disable_config()
        self.status_bar.showMessage('Disconnected...')
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def load_rotem_table(self):
        self.rotem_status_tabel.setRowCount(len(self._register_table))
        for reg in self._register_table:
            self.rotem_status_tabel.setItem(reg['row'],0,QTableWidgetItem(reg['Address']))
            self.rotem_status_tabel.setItem(reg['row'],1,QTableWidgetItem(reg['Description']))

    def modbus_connect(self):
        self.setCursor(QtCore.Qt.CursorShape.WaitCursor)
        sock,address = self.device_connect()
        if  sock is not None:
            self.load_rotem_table()
            self.address = address
            if self._rotem_thread is not None:
                self._rotem_thread.stop()

            self._rotem_thread = rotem_thread(sock, self.recv_status,tick=0.1, log = self.log, exit=self.stop, address = address)
            self._rotem_thread.modbus = self.recv_register
            self._rotem_thread._loss = self.disconnect
            self._rotem_thread.start()
            self._rotem_thread.command("info",self.update_device_info)
            self.enable_config()
        else:
            self.device_model.setText('No response from device')
            self.rotem_connect_status.setText('-')
            self.data_monitoring.appendPlainText("Cannot connect to device")
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def device_connect(self):
        if len(self.list_device.selectedIndexes())==1:
            if self._rotem_thread is not None and not self._rotem_thread.stopped():
                self._rotem_thread.stop()
            try:
                address = self._device[self.list_device.selectedIndexes()[0].row()]
                sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((address,8000))
                self.data_monitoring.appendPlainText(sock.recv(1024).decode().strip())
                self.status_bar.showMessage(f'Connect to {address}')
                return sock,address
            except Exception as ex:
                self.data_monitoring.appendPlainText('No response data from device!')
                self.log.error(ex)
                return (None,None)
        else:
            return (None,None)

    def update_device_info(self,recv=None):
        if recv is not None:
            self.log.debug(recv)
            try:
                model,dhcp,ip,sn,gw,mac,hostname,barn,baud = recv.split(',')
                self.device_model.setText(model)
                self.cb_dhcp_ip.setChecked(dhcp=="on")
                self.device_ip.setText(ip)
                self.device_gw.setText(gw)
                self.device_sn.setText(sn)
                self.device_mac.setText(mac)
                self.device_name.setText(hostname)
                self.rotem_bran_no.setValue(int(barn))
                self.rotem_baudrate.setCurrentText(baud)
                return True
            except Exception as ex:
                self.data_monitoring.appendPlainText("Cannot get information from device!")
                self.log.error(ex)
                return False
        else:
            self.device_model.clear()
            self.cb_dhcp_ip.setChecked(False)
            self.device_ip.clear()
            self.device_gw.clear()
            self.device_sn.clear()
            self.device_mac.clear()
            self.device_name.clear()
            self.rotem_bran_no.clear()
            self.data_monitoring.appendPlainText('Device disconnected!')

    def set_device_info(self):
        self.setCursor(QtCore.Qt.CursorShape.WaitCursor)
        self.data_monitoring.appendPlainText("Set configuration data")
        command = [
            f'mac={self.device_mac.text()}',
            f'dhcp={"on" if self.cb_dhcp_ip.isChecked() else "off"}',
            f'name={self.device_name.text()}',
            f'rotem.barn={self.rotem_bran_no.text()}',
            f'rotem.baud={self.rotem_baudrate.currentText()}']
        if not self.cb_dhcp_ip.isChecked():
            command.append(f'ip={self.device_ip.text()}/{self.device_sn.text()}/{self.device_gw.text()}')
        for c in command:
            self._rotem_thread.command(c,lambda recv : self.log.debug('OK' if recv == '\x06' else 'Error'))
            time.sleep(0.1)
        self._rotem_thread.command("save",lambda recv : self.data_monitoring.appendPlainText('OK' if recv == '\x06' else 'Error'))
        time.sleep(3)
        self._rotem_thread.command("reboot","reboot")
        time.sleep(1)
        self.disconnect()
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def find_device(self):
        self.setCursor(QtCore.Qt.CursorShape.WaitCursor)
        self.status_bar.showMessage('Finding device in network...')
        self._device.clear()
        self.list_device.clear()
        list = self.list_device
        self.update_device_info()
        self.disable_config()
        if(self.cb_interface_dev.currentIndex() in range(0,len(self._broadcast))):
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP) as sck:
                sck.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
                sck.bind((self._ip[self.cb_interface_dev.currentIndex()],0))
                # sck.bind(("0.0.0.0",0))
                sck.settimeout(1)
                ip = self._broadcast[self.cb_interface_dev.currentIndex()]
                self.log.debug(f'send broadcast to network : {ip}')
                sck.sendto(b'MCIINFO',(f"{'255.255.255.255'}",50001))
                while True:
                    try:
                        data,_ = sck.recvfrom(1024)
                        self.log.debug(f"{data.decode()}")
                        _,ip,_,_,hostname = data.decode().split(',')
                        list.addItem(f'{ip} ({hostname})')
                        self._device.append(ip)
                    except Exception as _:
                        break
        else:
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP) as sck:
                    sck.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
                    sck.settimeout(0.5)
                    self.log.debug(f'send broadcast all network.')
                    sck.bind((f"0.0.0.0",0))
                    sck.sendto(b'MCIINFO',(f"{'255.255.255.255'}",50001))
                    while True:
                        try:
                            data,_ = sck.recvfrom(1024)
                            self.log.debug(f"{data.decode()}")
                            _,ip,_,_,hostname = data.decode().split(',')
                            list.addItem(f'{ip} ({hostname})')
                            self._device.append(ip)
                        except Exception as _:
                            break
        self.status_bar.showMessage('Already...')
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    windows = MainWidows()
    windows.show()
    windows.list_ethernet_device()
    windows.find_device()
    app.exec()
    windows.stop.set()
    windows.log.debug("Bye")
        