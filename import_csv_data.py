# EVE Echoes map data import tool

# Standard libraries
import sqlite3
import csv
import logging

def main():
    init_logging()
    logging.debug("START")
    init_db()
    import_csv_data()
    logging.debug("DONE")

def init_logging():
    logformat="%(asctime)s %(levelname)s %(filename)s %(funcName)s %(message)s"
    logging.basicConfig(filename='log/import_csv_data.log',level=logging.INFO,format=logformat,filemode='w')
    logging.debug("===================================================================")
    logging.debug("Logging started")

def open_db():
    db_file="db/ee_map.db"
    logging.info("Using database file %s" % db_file)
    db = sqlite3.connect(db_file)
    return(db)

def close_db(db):
    db.close()
    logging.debug("Database closed")

def init_db():
    logging.info("Initializing database")
    db=open_db()
    c=db.cursor()

    logging.debug("Dropping old tables")
    c.execute('DROP TABLE IF EXISTS systems')
    c.execute('DROP TABLE IF EXISTS neighbors')
    c.execute('DROP TABLE IF EXISTS systemplanets')
    c.execute('DROP TABLE IF EXISTS neighbors')
    c.execute('DROP TABLE IF EXISTS planetary_production_data')

    # Systems
    sql="CREATE TABLE systems(sid INTEGER NOT NULL PRIMARY KEY, region TEXT, constellation TEXT, name TEXT, security REAL)"
    logging.debug("Create table SYSTEMS using %s" % sql)

    c.execute(sql)

    # Neighbors of systems
    # security level
    # 0 = -1.0 to 0
    # 1 = 0.1 to 0.4
    # 2 = 0.5 to 1
    sql="CREATE TABLE neighbors(sid INTEGER, nid INTEGER, s_security REAL)"
    logging.debug("Create table NEIGHBORS using %s" % sql)
    c.execute(sql)

    # Planets of system
    sql="CREATE TABLE systemplanets(sid INTEGER, pid INTEGER)"
    logging.debug("Create table SYSTEMPLANETS using %s" % sql)
    c.execute(sql)

    # Production info of planets
    logging.debug("Create table PLANETARY_PRODUCTION_DATA using %s" % sql)
    sql="CREATE TABLE planetary_production_data(pid INTEGER NOT NULL , name TEXT, type TEXT , resource TEXT, richness TEXT, output REAL)"
    c.execute(sql)

    db.commit()
    close_db(db)
    logging.info("Database initialized")

def import_csv_data():
    logging.info("Importing data")
    db = open_db()
    c=db.cursor()

    csv_file="csv/systems.csv"
    logging.info("Importing map data from %s" % csv_file)
    with open(csv_file, newline='') as file:
        data = csv.DictReader(file)
        for r in data:
            logging.debug("row: %s" % r)

            # Add systems
            sql='INSERT INTO systems (sid, region, constellation, name, security) VALUES (%s, "%s", "%s", "%s", %s)' % (r['ID'], r['Region'], r['Constellation'], r['Name'], r['Security'])
            logging.debug("Adding system data: %s" % sql)
            c.execute(sql)

            # Add neighbors
            if r['Neighbors']:
                logging.debug("Adding neighbors for system %s: %s" % (r['Name'], r['Neighbors'] ))
                for n in r['Neighbors'].split(':'):
                    sql='INSERT INTO neighbors (sid, nid, s_security) VALUES (%s, %s, %s)' % (r['ID'],n,r['Security'])
                    logging.debug("sql: %s" % sql)
                    c.execute(sql)
            else:
                logging.debug("System %s don't have any neighbors" % r['Name'])

            #Add planets of system
            if r['Planets']:
                logging.debug("Adding planets for system %s: %s" % (r['Name'], r['Planets']))
                for n in r['Planets'].split(':'):
                    sql='INSERT INTO systemplanets (sid, pid) VALUES (%s,%s)' % (r['ID'], n)
                    logging.debug("sql: %s" % sql)
                    c.execute(sql)
            else:
                logging.debug("System %s don't have any planets" % r['Name'])

    # Add production data for planets
    csv_file="csv/production.csv"
    logging.info("Importing production data for planets from %s" % csv_file)
    with open (csv_file, newline='') as file:
        data = csv.DictReader(file)
        for r in data:
            sql='INSERT INTO planetary_production_data (pid,name,type,resource,richness,output) VALUES (%s,"%s","%s","%s","%s",%s)' % (r['Planet ID'],r['Planet Name'],r['Planet Type'],r['Resource'],r['Richness'],r['Output'])
            logging.debug("sql: %s" % sql)
            c.execute(sql)

    db.commit()
    close_db(db)
    logging.info("Data imported")




if __name__ == "__main__":
    main()
