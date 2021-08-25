# EVE Echoes data tool by Kai Käpölä

# Standard modules
import sqlite3
import os
from datetime import datetime
import logging
import sys
import json

# PIPed modules
import networkx as nx
import scipy
import matplotlib.pyplot as plt
import numpy as np
import beepy

def init_logging():
    logformat="%(asctime)s %(levelname)s %(filename)s %(funcName)s %(message)s"
    logging.basicConfig(filename='log/analyze.log',level=logging.DEBUG,format=logformat,filemode='w')
    logging.debug("\n\n\n===================================================================")
    logging.debug("Logging started")

def open_db():
    db_file="db/ee_map.db"
    logging.info("Using database file %s" % db_file)
    db = sqlite3.connect(db_file)
    return(db)

def close_db(db):
    db.close()
    logging.debug("Database closed")

def get_shortest_path_and_lenght(MAP,start_node,end_node,security):
    logging.info("Searching shortest from node %s to %s using security %s..." % (start_node,end_node,security))
    if security=="SHORT":
        path=nx.shortest_path(MAP,source=start_node,target=end_node)
    elif security=="SAFE":
        path=nx.dijkstra_path(MAP,source=start_node,target=end_node,weight="security")
    else:
        logging.error("Unknown security type %s" % security)
        exit(1)
    return(path,len(path))

def print_path(MAP,path):
    lgging.debug("Print map for path: %s" % path)
    for n in path:
        sql="SELECT sid,region,constellation,name,security FROM systems WHERE sid=%s" % (n)
        cursor.execute(sql)
        for i in cursor:
            print(i['sid'],i['region'],i['constellation'],i['name'],i['security'])
            for e in MAP.edges(i):
                print ("---",e,MAP.get_edge_data(e[1],e[0]),MAP.get_edge_data(e[0],e[1]))

def printf(txt):
    print(txt,end="")

def analyze():
    db = open_db()
    c1=db.cursor()
    c2=db.cursor()

    # Systems with route to another region
    print ("Systems with route to another regions")
    sql="SELECT s.sid,s.region, n.nid,s2.region FROM systems s JOIN neighbors n ON s.sid = n.sid JOIN systems s2 ON s2.sid=n.nid AND s.region<>s2.region ORDER BY s.region"
    for s in c1.execute(sql):
        print (s)

    # Links to another regions per region
    print ("Number of links to another region per region")
    sql="SELECT s.region,count(s2.region) AS links FROM systems s JOIN neighbors n ON s.sid = n.sid JOIN systems s2 ON s2.sid=n.nid AND s.region<>s2.region GROUP BY s.region ORDER BY links"
    for s in c1.execute(sql):
        print (s)

    close_db(db)

def read_map_cache(type):

    logging.debug("Looking for %s map cache file" % type)

    file1="cache/ee_map_cache_%s.gpickle" % type
    file2="cache/ee_map_cache_%s.yaml" % type

    if os.path.exists(file1):
        logging.info("Reading Pickled map data from %s" % file1)
        MAP=nx.read_gpickle(file1)
        logging.debug("Loaded %s systems from %s cache map file" % (len(MAP),type))
    elif os.path.exists(file2):
        logging.info("Reading YAML map data from %s" % file2)
        MAP=nx.read_yaml(file2)
        logging.debug("Loaded %s systems from %s cache map file" % (len(MAP),type))
    else:
        logging.info("No cached %s map file found." % type)
        MAP=None

    return(MAP)

def write_map_cache(MAP,type):
    # Save MAP data
    logging.info("Writing %s map data to cache files" % type)

    file1="cache/ee_map_cache_%s.gpickle" % type
    file2="cache/ee_map_cache_%s.yaml" % type

    logging.debug("Writing map data into PICKLE file %s" % file1)
    nx.write_gpickle(MAP, file1)
    logging.debug("Writing map data into YAMLE file %s" % file2)
    nx.write_yaml(MAP, file2)
    logging.info("Cache files writen")

def read_base_map_data(db):

    logging.debug("Reading map data to memory from database")
    MAP = nx.MultiDiGraph()

    db.row_factory = sqlite3.Row
    c1=db.cursor()

    # Create nodes
    logging.info("Reading nodes from database")
    sql="SELECT sid,region,constellation,name,security FROM systems"
    #logging.debug("sql: %s" % sql)
    for n in c1.execute(sql):
        MAP.add_node(n['sid'],region=n['region'],constellation=n['constellation'],name=n['name'],security=n['security'])

    # Create edges
    logging.info("Creating edges")
    sql="SELECT nid,sid,s_security FROM neighbors"
    #logging.debug("sql: %s" % sql)
    for n in c1.execute(sql):
        #print(list(n))
        if n['s_security'] <= 0:
            w1=1000000
            w2=1000000 # High sec only
        elif n['s_security'] < 0.5:
            w1=1000
            w2=1000000 # High sec only
        else:
            w1=1
            w2=1
        MAP.add_edge(n['nid'],n['sid'],security=w1,security_hisec_only=w2,security_level=n['s_security'])

    return(MAP)
    logging.info("Basic map structure ready in memory")

def get_longest_path(MAP):
    # Find longest path
    logging.debug("Searching for longest path")
    all_paths = dict(nx.all_pairs_shortest_path_length(MAP))
    max_jumps=0
    for n in all_paths:
        mx=max(list(all_paths[n].values()))
        if mx>max_jumps:
            max_jumps=mx
    logging.debug("Found %s jumps long path." % (max_jumps))
    return(max_jumps)

def add_production_data(db,MAP):
# Add production data for planets
    logging.info("Adding planetary production data for %s systems" % len(MAP.nodes))
    c1=db.cursor()
    for n in MAP:
        sql="SELECT p.pid,p.resource,p.output FROM systems s JOIN systemplanets sp ON s.sid=sp.sid AND s.sid=%s JOIN planets p ON sp.pid=p.pid" % (n)
        #logging.debug("sql: %s" % sql)
        c1.row_factory = lambda cursor, row: row
        s=c1.execute(sql).fetchall()
        MAP.nodes[n]['planets']=s
    logging.info("Planetary production data added")

def get_path_edges(MAP,path):
    # Collect path edges for drawing
    logging.debug("Collecting edges for path: %s" % path)
    path_edges=[]
    for n in range(0,len(path)-1):
        path_edges.append((path[n],path[n+1]))
    logging.debug("Found %s edges" % len(path_edges))
    logging.debug("Path edges: %s" % path_edges)
    return(path_edges)

def get_constellations_on_path(MAP,path):
    # Collect constellations along path
    logging.debug("Collecting constellations for path: %s" % path)
    constellations=[]
    for p in [path]:
        for n in p:
            if not MAP.nodes[n]['constellation'] in constellations :
                constellations.append(MAP.nodes[n]['constellation'])
    logging.debug("Found %s constellations: %s" % (len(constellations), constellations))
    return(constellations)

def get_all_constellations(MAP):
    logging.debug("Collecting all constellations")
    constellations=[]
    for n in MAP:
        if not MAP.nodes[n]['constellation'] in constellations :
            constellations.append(MAP.nodes[n]['constellation'])
    logging.debug("Found %s constellations: %s" % (len(constellations), constellations))
    return(constellations)

def get_all_regions(MAP):
    logging.debug("Collecting all regions")
    regions=[]
    for n in MAP:
        if not MAP.nodes[n]['region'] in regions :
            regions.append(MAP.nodes[n]['region'])
    logging.debug("Found %s regions: %s" % (len(regions), regions))
    return(regions)

def remove_nodes(MAP,nodelist):
    if nodelist:
        logging.debug("Removing %s nodes from map" % len(nodelist))
        MAP.remove_nodes_from(nodelist)
        logging.debug("Nodes removed")
    else:
        logging.debug("No nodes to remove from map")

def get_nodes_of_constellation(MAP,constellation):
    logging.debug("Collecting all nodes of constellation %s" % constellation)
    nodes=[]
    for n in MAP:
        if MAP.nodes[n]['constellation'] == constellation:
            nodes.append(n)
    logging.debug("Found %s nodes from constellation %s" % (len(nodes), constellation))
    return(nodes)

def get_nodes_of_region(MAP,region):
    logging.debug("Collecting all nodes of region %s" % region)
    nodes=[]
    for n in MAP:
        if MAP.nodes[n]['region'] == region:
            nodes.append(n)
    logging.debug("Found %s nodes from region %s" % (len(nodes), region))
    return(nodes)

def remove_nodes_without_edge(MAP):
    logging.debug("Removing nodes without edge")
    c=0
    TMAP = MAP.copy()
    for n in TMAP:
        if TMAP.degree(n) == 0:
            MAP.remove_node(n)
            c=c+1
    logging.debug("Removed %s nodes from map" % c)

def generate_node_labels(MAP):
    # Node texts
    logging.debug("Generating node labes")
    node_labels=nx.get_node_attributes(MAP, 'name')
    for n in MAP:
        sec=MAP.nodes[n]['security']
        cons=MAP.nodes[n]['constellation']
        reg=MAP.nodes[n]['region']
        node_labels[n]=node_labels[n]+"\n"+cons+"\n"+reg+"\n"+str(sec)
    return(node_labels)

def get_nodes_grouped_by_security(MAP):
    # Nodes per security level
    logging.debug("Grouping nodes to nul, low and high security groups")
    nl=MAP.nodes()
    nulsec_nodes=[]
    lowsec_nodes=[]
    highsec_nodes=[]
    for n in MAP.nodes():
        if MAP.nodes[n]['security']<=0:
            nulsec_nodes.append(n)
        elif MAP.nodes[n]['security']<0.5:
            lowsec_nodes.append(n)
        else:
            highsec_nodes.append(n)
    logging.debug("Found %s nulsec, %s lowsed and %s highsec nodes" % (len(nulsec_nodes), len(lowsec_nodes), len(highsec_nodes)))
    return(nulsec_nodes, lowsec_nodes, highsec_nodes)

def draw_edges(MAP,pos,line_width,line_color,edges=""):
    logging.debug("Drawing %s edges using width %s and color %s" % (len(edges),line_width,line_color))
    if edges=="":
        logging.debug("Drawing all edges")
        nx.draw_networkx_edges(MAP, pos=pos,arrows=False,width=line_width,edge_color=line_color)
    else:
        logging.debug("Drawing %s edges" % len(edges))
        nx.draw_networkx_edges(MAP, pos=pos,arrows=False,edgelist=edges,width=line_width,edge_color=line_color)

def draw_nodes(MAP,pos,nodesize,nodecolor,nodes=""):
    logging.debug("Drawing %s nodes of size %s using color %s" % (len(nodes),nodesize,nodecolor))
    if nodes=="":
        nx.draw_networkx_nodes(MAP, pos=pos,node_size=nodesize,node_color=nodecolor)
    else:
        nx.draw_networkx_nodes(MAP, pos=pos,nodelist=nodes,node_size=nodesize,node_color=nodecolor)

def draw_labels(MAP,pos,fontsize,labellist):
    logging.debug("Drawing %s labels of size %s" % (len(labellist),fontsize))
    nx.draw_networkx_labels(MAP,pos=pos,labels=labellist,font_size=fontsize,verticalalignment='top')

def save_map_picture(name,type,date_mode):
    t=datetime.now().strftime("%Y-%m-%d-%I-%M-%S.%f")
    if date_mode:
        filename="pics/"+name+"_"+t+"."+type
    else:
        filename="pics/"+name+"."+type

    logging.debug("Saving map to file %s" % filename)
    plt.savefig(filename)
    logging.debug("File %s saved" % filename)

def generate_constellation_maps(MAP,date_mode):
    for c in get_all_constellations(MAP):
        print("Generating map for constellation %s" % c)
        logging.info("Generating map for constellation %s" % c)
        nodes = get_nodes_of_constellation(MAP,c)
        C = MAP.__class__()
        C.add_nodes_from((n, MAP.nodes[n]) for n in nodes)
        C.add_edges_from((n, nbr, key, d)
            for n, nbrs in MAP.adj.items() if n in nodes
            for nbr, keydict in nbrs.items() if nbr in nodes
            for key, d in keydict.items())

        node_labels = generate_node_labels(C)
        nulsec_nodes,lowsec_nodes,highsec_nodes=get_nodes_grouped_by_security(C)

        plt.figure(figsize=(16,16),dpi=100,frameon=0)
        pos=nx.kamada_kawai_layout(C,weight="")
        print("Drawing edges")
        draw_edges(C,pos,1,"#202020")
        print("Black nulsec nodes")
        draw_nodes(C,pos,70,"#000000",nulsec_nodes)
        print("Red lowsec nodes")
        draw_nodes(C,pos,70,"#FF0000",lowsec_nodes)
        print("Green hisec nodes")
        draw_nodes(C,pos,70,"#00FF00",highsec_nodes)
        print("Node labes")
        draw_labels(C,pos,20,node_labels)

        save_map_picture("ee_map_constellation_%s" % c,"jpg",date_mode)

def generate_all_region_maps(MAP,date_mode):
    for c in get_all_regions(MAP):
        print("Generating map for region %s" % c)
        logging.info("Generating map for region %s" % c)

def generate_region_map(MAP,region_name,date_mode):
    region_nodes = get_nodes_of_region(MAP,region_name)
    C = MAP.__class__()
    C.add_nodes_from((n, MAP.nodes[n]) for n in region_nodes)
    C.add_edges_from((n, nbr, key, d)
        for n, nbrs in MAP.adj.items() if n in region_nodes
        for nbr, keydict in nbrs.items() if nbr in region_nodes
        for key, d in keydict.items())

    node_labels = generate_node_labels(C)
    nulsec_nodes,lowsec_nodes,highsec_nodes=get_nodes_grouped_by_security(C)


    plt.figure(figsize=(16,16),dpi=200,frameon="False")
    plt.text(-1,-1, region_name, fontsize=40,horizontalalignment="left")
    pos=nx.kamada_kawai_layout(C,weight="")
    #pos=nx.spring_layout(C)
    print("Drawing edges")
    draw_edges(C,pos,1,"#808080")
    print("Black nulsec nodes")
    draw_nodes(C,pos,50,"#808080",nulsec_nodes)
    print("Red lowsec nodes")
    draw_nodes(C,pos,50,"#FF0000",lowsec_nodes)
    print("Green hisec nodes")
    draw_nodes(C,pos,50,"#00FF00",highsec_nodes)
    print("Node labes")
    draw_labels(C,pos,5,node_labels)

    save_map_picture("ee_map_region_%s" % region_name,"jpg",date_mode)
    plt.close()

def generate_full_map(MAP,date_mode):

        print("Generating full map")
        logging.info("Generating full map")

        node_labels = generate_node_labels(MAP)
        nulsec_nodes,lowsec_nodes,highsec_nodes=get_nodes_grouped_by_security(MAP)

        plt.figure(figsize=(16,16),dpi=200,frameon="False")
        pos=nx.kamada_kawai_layout(MAP,weight="")
        #pos=nx.spring_layout(MAP,k=100)
        print("Drawing edges")
        draw_edges(MAP,pos,1,"#808080")
        print("Black nulsec nodes")
        draw_nodes(MAP,pos,50,"#808080",nulsec_nodes)
        print("Red lowsec nodes")
        draw_nodes(MAP,pos,50,"#FF0000",lowsec_nodes)
        print("Green hisec nodes")
        draw_nodes(MAP,pos,50,"#00FF00",highsec_nodes)
        print("Node labes")
        draw_labels(MAP,pos,5,node_labels)

        save_map_picture("ee_map_full","jpg",date_mode)
        plt.close()

def convert_node_name_to_id(MAP,name):
    for nid, attrs in MAP.nodes.data():
        #print (nid,attrs['name'],name)
        if attrs['name'].lower() == name.lower():
            return (nid)
    return(0)

def load_map():
    logging.info("Loading map")

    # Database from EE data
    db = open_db()

    # NetworkX map for map stucture
    MAP = nx.MultiDiGraph()
    logging.debug("Using NetworkX %s" % type(MAP))

    print("Loading map data")
    MAP = read_map_cache("standard")
    if not MAP:
        logging.debug("Cache map file not found. Generating new cache map file(s).")
        MAP = read_base_map_data(db)
        write_map_cache(MAP,"base_clean")
        print("Add production data for nodes")
        add_production_data(db,MAP)
        print("Add production data for edges")
        add_production_weight_for_edges(db,MAP)
        write_map_cache(MAP,"base_production")
        print("Remove nodes without edge")
        remove_nodes_without_edge(MAP)
        write_map_cache(MAP,"standard")
        print("Map data ready")

    logging.info("Map loaded")
    return(MAP)

def generate_shortest_path_between_two_nodes(MAP,start_node_name,end_node_name):

    start = convert_node_name_to_id(MAP,start_node_name)
    end = convert_node_name_to_id(MAP,end_node_name)

    print("Get safe and short paths and edges")
    short_path_nodes, short_path_lenght = get_shortest_path_and_lenght(MAP,start,end,"SHORT")
    short_path_edges = get_path_edges(MAP,short_path_nodes)
    safe_path_nodes, safe_path_lenght = get_shortest_path_and_lenght(MAP,start,end,"SAFE")
    safe_path_edges = get_path_edges(MAP,safe_path_nodes)

    # Temporally map
    C = MAP.copy()

    print("Collect visited constellations")
    visited_constellations = get_constellations_on_path(MAP,short_path_nodes)
    visited_constellations = visited_constellations + get_constellations_on_path(MAP,safe_path_nodes)
    all_constellations = get_all_constellations(MAP)
    for ac in all_constellations:
        if not ac in visited_constellations:
            constellation_nodes = get_nodes_of_constellation(MAP,ac)
            C.remove_nodes_from(constellation_nodes)

    node_labels = generate_node_labels(C)
    nulsec_nodes,lowsec_nodes,highsec_nodes=get_nodes_grouped_by_security(C)

    plt.figure(figsize=(16,16),dpi=200,frameon="False")
    pos=nx.kamada_kawai_layout(C,weight="")
    #pos=nx.spring_layout(C)
    print("Drawing edges")
    draw_edges(C,pos,1,"#808080")
    print("Black nulsec nodes")
    draw_nodes(C,pos,50,"#808080",nulsec_nodes)
    print("Red lowsec nodes")
    draw_nodes(C,pos,50,"#FF0000",lowsec_nodes)
    print("Green hisec nodes")
    draw_nodes(C,pos,50,"#00FF00",highsec_nodes)
    print("Node labes")
    draw_labels(C,pos,5,node_labels)
    print("Short path edges")
    draw_edges(C,pos,5,"#FF0000",short_path_edges)
    print("Safe path edges")
    draw_edges(C,pos,5,"#00FF00",safe_path_edges)
    save_map_picture("ee_map_shortest_path_from_%s_to_%s" % (start_node_name,end_node_name),"jpg",False)
    plt.close()


def add_production_weight_for_edges(MAP):
    logging.info ("Adding planetary production data for edges")

    for e in MAP.edges():
        #print("Edge:",e)
        edge_p1 = get_planetary_production(MAP,e[0]) # Start node of edge
        edge_p2 = get_planetary_production(MAP,e[1]) # End node of edge
        #print("p1=",p1)
        #print("p2=",p2)

        # COllect
        materials = []
        materials.extend(edge_p1.keys())
        materials.extend(edge_p2.keys())
        materials = list(set(materials)) # Remove duplicate materials


        # Count average of average
        md={}
        for m in materials:
            if m in p1 and m in p2:
                mp=(p1[m] + p2[m])/2
            elif m in p1:
                mp = p1[m]/2
            else:
                mp = p2[m]/2
            md[m] = mp
        print("\nmd=",md)

        at={}
        at[e]=md
        at[(30000003, 30000001)]=md
        print("at=",at)

        bb=datetime.now()
        print("\nbb=",bb)
        nx.set_edge_attributes(MAP,bb,"now")
        ea=nx.get_edge_attributes(MAP,(30000003, 30000001))
        print("\nEdgeAttr:",ea)


        exit(1)


    logging.info ("Planetary production weights ready")

def get_planetary_production(MAP,node):

    m={}
    for p in MAP.nodes[node]['planets']:

        planet_id = p[0]
        mineral_name = p[1]
        mineral_production = p[2]
        logging.debug("Planet %s have production level %s for mineral %s" % (planet_id, mineral_production, mineral_name))

        if mineral_name not in m:
            m[mineral_name] = mineral_production
        else:
            m[mineral_name] = m[mineral_name] + mineral_production
    return(m)




def main():
    init_logging()
    logging.info ("START")

    MAP = load_map()

    home_name = 'Tash-Murkon Prime'
    target_name = 'Pator'

    add_production_weight_for_edges(MAP)

    # List here all working functions
    #generate_shortest_path_between_two_nodes(MAP,home_name,target_name)
    #generate_region_maps(MAP,False)
    #generate_constellation_maps(MAP,False)
    #generate_full_map(MAP,False)
    #generate_region_map(MAP,"Tash-Murkon",False)

    beepy.beep(5)
    logging.info ("END")


if __name__ == "__main__":
    main()
