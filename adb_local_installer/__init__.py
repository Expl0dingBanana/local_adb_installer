from adb_local_installer.connection import ADBConnection


with ADBConnection("a95x01", domain="dohmens.local") as conn:
    print(conn.conn)