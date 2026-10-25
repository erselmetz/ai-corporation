"""One authoritative QLockFile; same-user local socket only signals new chat."""
import hashlib
from PySide6.QtCore import QObject, QLockFile, Signal, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class Instance(QObject):
    activated = Signal()

    def __init__(self, data):
        super().__init__()
        data.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(data / 'desktop.lock'))
        self.name = 'erselmetz-' + hashlib.sha256(str(data.resolve()).casefold().encode()).hexdigest()[:24]
        self.server = QLocalServer(self)
        self.peers = set()
        self.server.setMaxPendingConnections(16)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.accept)

    def acquire_or_notify(self):
        if not self.lock.tryLock(0):
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if not socket.waitForConnected(2000):
                raise RuntimeError('ERSELMETZ AI is opening or closing. Try again shortly.')
            socket.write(b'new-chat\n'); socket.flush(); socket.waitForBytesWritten(1000)
            if not socket.waitForReadyRead(2000) or bytes(socket.readAll()) != b'ok\n':
                raise RuntimeError('The existing workspace did not acknowledge the new window. Try again shortly.')
            socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise RuntimeError('The local window channel could not start.')
        return True

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if len(self.peers) >= 16:
                socket.abort(); socket.deleteLater(); continue
            self.peers.add(socket)
            timeout = QTimer(socket); timeout.setSingleShot(True); timeout.timeout.connect(socket.abort); timeout.start(2000)
            socket.setReadBufferSize(65)
            socket.setProperty('command', b'')
            socket.readyRead.connect(lambda s=socket: self.read(s))
            socket.disconnected.connect(socket.deleteLater)
            socket.disconnected.connect(lambda s=socket: self.peers.discard(s))
            self.read(socket)

    def read(self, socket):
        command = socket.property('command') + bytes(socket.readAll())
        socket.setProperty('command', command)
        if command == b'new-chat\n':
            socket.write(b'ok\n'); socket.flush()
            self.activated.emit(); socket.disconnectFromServer()
        elif len(command) > 64 or b'\n' in command:
            socket.abort()

    def close(self):
        for peer in list(self.peers): peer.abort()
        self.server.close(); self.lock.unlock()
