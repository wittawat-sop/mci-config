import socket
import os,logging
class Bootloader():
    def __init__(self,log:logging=None):
        self.log = log
        with open('D:\WIZnet\MC Intellisense_boot\Objects\ROTEM.bin',"rb") as fp:
            file_size = (os.fstat(fp.fileno()).st_size)
            if self.log is not None: 
                self.log.debug(f'file size = {file_size} Bytes')
                self.log.debug(f'file len = {len(fp.read())}')
            pass


if __name__ == "__main__":
    print("bootloader module is running")
    logging.basicConfig(level=logging.DEBUG,format='%(module)15s %(levelname)s - %(funcName)20s - %(lineno)4d - %(message)s ')
    bl = Bootloader(logging)

