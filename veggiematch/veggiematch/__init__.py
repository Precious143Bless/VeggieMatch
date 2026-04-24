# Required only if you installed PyMySQL instead of mysqlclient.
# If you installed mysqlclient, you can leave this file empty.
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
