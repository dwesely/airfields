# -*- coding: utf-8 -*-
"""
Created on Fri Aug 21 06:34:14 2015

Downloads and parses abandoned airport lists from http://www.airfields-freeman.com
Compares BTS and NFDC airport lists
Compares abandoned airport lists to list of "likely closed" airfields
Writes results to kml

BTS Master Coordinate Table available for download here: https://www.transtats.bts.gov/Tables.asp?DB_ID=595
NFDC APT.txt file available for download here: https://nfdc.faa.gov/xwiki/bin/view/NFDC/28DaySub-2017-08-17

Latest missing airfield results: https://drive.google.com/open?id=1pEgmk0KaD5EHEsIV-9tOjZyoTw0&usp=sharing

@author: Wesely
"""

import urllib2
import re
import os
from bs4 import BeautifulSoup
import datetime
import glob
import csv
import pprint
import numpy as np

base_url = "http://www.airfields-freeman.com/"    


def haversine_np(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)

    All args must be of equal length.    

    """
    #https://stackoverflow.com/questions/29545704/fast-haversine-approximation-python-pandas
    
    #make the first value the same length as the second
    if type(lon2) is list and type(lon1) is not list:
        lon1 = [lon1]*len(lon2)
        lat1 = [lat1]*len(lon2)
        
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2

    c = 2 * np.arcsin(np.sqrt(a))
    km = 6367 * c
    return km
    

def get_link_from_html(text):
    """Parse href link text out of html text"""
    cell_links = re.findall('href="([^.]+.htm)"',text)
    return cell_links[0]
    

def get_mdyyyy_from_text(text):
    """Parse m/d/yyyy from text and return date object"""
    cell_dates  = re.findall('\d+/\d+/\d+',text)
    update_date = datetime.datetime.strptime(cell_dates[0], "%m/%d/%y").date()
    if update_date.year > 2050:
       update_date = update_date.replace(year=update_date.year-100)
    return update_date


def get_latest_file(string):
    """Look for matching files and return the most recent"""
    files = filter(os.path.isfile, glob.glob('./' + string))
    sorted_dates = sorted([os.path.getmtime(item) for item in files])
    if sorted_dates:
        return datetime.datetime.fromtimestamp(sorted_dates[-1]).date()
    return datetime.date(1, 1, 1)


def scrape_airports():
    """Download new files from Abandoned Airfields website"""
    #Checks update times, compares to file dates, only downloads updated pages
    #TODO: Check robots.txt to see if it was changed to disallow robots
    print('Checking for updated files...')
    total_downloaded = 0
    response  = urllib2.urlopen(base_url)
    home_page = response.read()
    total_downloaded = total_downloaded + len(home_page)
    #links     = re.findall('HREF="([^.]+).htm"',home_page)
    #print(links)
    
    home_soup = BeautifulSoup(home_page, 'html.parser')
    state_cells = home_soup.find_all('td')
    
    #check this state for updates
    for state_cell in state_cells:
        #print(state_cell)
        deep_link = get_link_from_html(repr(state_cell))
        state,state_file = deep_link.split('/')
        
        update_date = get_mdyyyy_from_text(repr(state_cell))
        
        local_date = get_latest_file(state_file.replace('.htm','*.htm'))

        #print('{} last updated {}, local version updated {}'.format(deep_link,update_date,local_date))
        
        if update_date > local_date:
            print('{} last updated {}, local version updated {}'.format(deep_link,update_date,local_date))
            this_link  = '{}{}'.format(base_url,deep_link)
            response   = urllib2.urlopen(this_link)
            state_page = response.read()
            total_downloaded = total_downloaded + len(state_page)
            
            state_soup = BeautifulSoup(state_page, 'html.parser')
            region_cells = state_soup.find_all('td')
            if not region_cells:
                #No cells here, must be a state without separate regions
                airport_file = open('./{}'.format(state_file),'w')
                airport_file.write(state_page)
                airport_file.close()
                continue
                
            #check this state for updates
            for region_cell in region_cells:
                #print(region_cell)
                try:
                    region_link = get_link_from_html(repr(region_cell))
                except:
                    print("No link in this cell, skipping. This should be fine.")
                    continue
                update_date = get_mdyyyy_from_text(repr(region_cell))
                
                local_date = get_latest_file(region_link)
                print('{} last updated {}, local version updated {}'.format(region_link,update_date,local_date))
                if update_date > local_date:
                    this_deep_link = '{}{}/{}'.format(base_url,state,region_link)
                    print(this_deep_link)
                    try:
                        response     = urllib2.urlopen(this_deep_link)
                    except:
                        print('Error downloading, skipping.')
                        continue
                    region_page  = response.read()
                    total_downloaded = total_downloaded + len(region_page)
                    airport_file = open('./{}'.format(region_link),'w')
                    airport_file.write(region_page)
                    airport_file.close()
    print('Downloaded {:.2}MB, please donate at {} to help with bandwidth costs!'.format(total_downloaded/(1024*1024.0),base_url))


def write_leaflet_file(items):
    """Write lat/lon items to get put into a leaflet map"""
    print('Writing leaflet file...')
    leaflet_output_file = open('./leaflet_code.txt','w')
    for item in items:
        leaflet_output_file.write("L.marker([{}, {}]).addTo(map)\n    .bindPopup('<a href=\"{}\">{}</a>')\n    .openPopup();\n".format(item.get('lat'),item.get('lon'),item.get('link'),item.get('airport')))
    leaflet_output_file.close()
    print('Done writing leaflet file.')
    
    
def write_kml_file(items,base_name='abandoned_airports'):
    """Write Google Earth kml file to import into Google Maps"""
    print('Writing kml files...')
    kml_output_file = open('./%s.kml'%base_name,'w')
    kml_head = '''<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
<Document><name>%s</name>
	<Style id="sh_airports"><IconStyle><scale>1.4</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/airports.png</href></Icon><hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/></IconStyle><ListStyle></ListStyle></Style>
	<Style id="sn_airports"><IconStyle><scale>1.2</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/airports.png</href></Icon><hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/></IconStyle><ListStyle></ListStyle></Style>
	<StyleMap id="msn_airports"><Pair><key>normal</key><styleUrl>#sn_airports</styleUrl></Pair><Pair><key>highlight</key><styleUrl>#sh_airports</styleUrl></Pair></StyleMap>
  '''%base_name
    kml_output_file.write(kml_head)
    recorded_states = dict()
    sorted_items = sorted(zip([item.get('state') for item in items],items))
    

    for state,item in sorted_items:
        if recorded_states and state not in recorded_states:
            kml_output_file.write('</Folder>\n')
            
            kml_state_output_file.write('</Folder>\n')
            kml_state_output_file.write('</Document></kml>')
            kml_state_output_file.close()
        if state not in recorded_states:
            kml_output_file.write('<Folder><name>{}</name><open>0</open>\n'.format(state))
            recorded_states[state] = 1
    
            kml_state_output_file = open('./{}_{}.kml'.format(base_name,state),'w')
            kml_state_output_file.write(kml_head)
            kml_state_output_file.write('<Folder><name>{}</name><open>0</open>\n'.format(state))
        else:
            recorded_states[state] = recorded_states[state] + 1
        placemark = '<Placemark><name>{}</name><description><![CDATA[<a href="{}">{}</a>]]></description><styleUrl>#msn_airports</styleUrl><Point><gx:drawOrder>1</gx:drawOrder><coordinates>{},{},0</coordinates></Point></Placemark>\n'.format(item.get('airport').replace('&',' and '),item.get('link'),'Link',item.get('lon'),item.get('lat'))
        kml_output_file.write(placemark)
        kml_state_output_file.write(placemark)
    kml_output_file.write('</Folder>\n')
    kml_output_file.write('</Document></kml>')

    kml_output_file.close()
    print(recorded_states)
    print('Done writing kml files.')
    
    
def write_csv_file(items):
    """Write the list of airports as csv"""    
    print('Writing csv files...')
    csv_output_file = open('./abandoned_airports.csv','w')
    csv_head = 'State,Airport,Lat,Lon,Link\n'
    csv_output_file.write(csv_head)
    for item in items:
        #print(type(item),item)
        csv_output_file.write('"{}","{}",{},{},"{}"\n'.format(item.get('state'),item.get('airport'),item.get('lat'),item.get('lon'),item.get('link')))
    csv_output_file.close()
    print('Done writing csv file.')
    
    
def read_airport_files():
    """Parse the downloaded airport files and save details"""
    print('Reading airport files...')
    #TODO: Speed this up
    airport_list = []

    #get list of files
    #Loop through all .htm files
    #check for airport name, lat/lon, link
    for thisFilename in os.listdir("./"):
        if thisFilename.endswith(".htm"):
            #print(thisFilename)
            thisFile = open(thisFilename,'r+')
            #print('Parsing {}...'.format(thisFilename))
            trimmed_html = re.sub(r'\s+',' ',thisFile.read().replace('\n',' '))
            soup = BeautifulSoup(trimmed_html, 'html.parser')
            
            trimmed_text = soup.get_text()
            airports = re.findall(r'_+_\s+([^_]{0,200}[)A-Z])\s+(-?\d+[.]?\d+)\s*[NnOoRrTtHh]*\s*[,/]\s*(-?\d+[.]?\d+)\s+(\S+)',repr(trimmed_text))
            state = re.findall(r'Airfields_([A-Z]+)_?',thisFilename)
            state = state[0]
            link = '{}{}/{}'.format(base_url,state,thisFilename)
                
            for airport,lat,lon,lon_direction in airports:
                #TODO: check longitude direction East vs. West, this if statement is hacky
                if float(lon) > 0 and float(lon) < 135:
                    """Longitude should be in the Western Hemisphere"""
                    lon = '-%s'%lon
                airport_list.append({'airport':airport, 'lat':lat, 'lon':lon, 'state':state, 'link':link})
            pass
    print('Done reading airport files.')
    return airport_list


def compare_locations(airports,test_airports,filter_dist=5):
    """Check Abandoned Airfields locations against BTS and NFDC airport locations"""
    airport_lat,airport_lon = get_lat_lon_from_list(airports)
    missing_items = []
    print('Closed,Start Date,Through Date,State,City,Name,lat,lon,link')
    for test_airport in test_airports:
        lon1 = test_airport.get('lon')
        lat1 = test_airport.get('lat')
        distances = haversine_np(lon1, lat1, airport_lon, airport_lat)
        closest = min(distances)
        if closest > filter_dist:# and test_airport.get('closed') == '1':
            missing_items.append({'airport':"{} ({})".format(test_airport.get('airport')), 
                                  'lat':test_airport.get('lat'), 
                                  'lon':test_airport.get('lon'), 
                                  'state':test_airport.get('state'),
                                  'city':test_airport.get('city'),
                                  'closed':test_airport.get('closed'),
                                  'start':test_airport.get('start'),
                                  'id':test_airport.get('id'),
                                  'link':test_airport.get('link')})

            print('"{}","{}","{}","{}","{}","{} ({})",{},{},"{}"'.format(
                test_airport.get('closed'),
                test_airport.get('start'),
                test_airport.get('thru'),
                test_airport.get('state'),
                test_airport.get('city'),
                test_airport.get('airport'), 
                test_airport.get('id'), 
                test_airport.get('lat'), 
                test_airport.get('lon'), 
                test_airport.get('link')))
    #TODO: sort by state before writing to kml
    write_kml_file(missing_items,base_name='missing_items')
    return missing_items

def get_bts_airport_list():
    """Read BTS Master Coordinates list and return airport details
    Source: https://www.transtats.bts.gov/DL_SelectFields.asp?Table_ID=288&DB_Short_Name=Aviation%20Support%20Tables"""
    #TODO: Download an updated file from https://www.transtats.bts.gov/DL_SelectFields.asp?Table_ID=288&DB_Short_Name=Aviation%20Support%20Tables
    #TODO: Allow closed or open runways to be returned
    airport_list = []
    with open('737306034_T_MASTER_CORD.csv', 'rb') as csvfile:
        bts_airports = csv.reader(csvfile, delimiter=',', quotechar='"')
        #Col 27: AIRPORT_IS_LATEST
        #Col  7: AIRPORT_COUNTRY_CODE_ISO
        #Col 18: lat
        for row in [row for row in bts_airports if row[7] == 'US' and '.' in row[18] and row[27] == '1']:
            #print ', '.join(row)
            airport_list.append({'airport':row[3], 
                                 'lat':float(row[18]), 
                                 'lon':float(row[23]), 
                                 'link':'https://skyvector.com/?ll=%s,%s&chart=301&zoom=1'%(row[18],row[23]),
                                 'state':row[9], 
                                 'city':row[4],
                                 'start':row[24],
                                 'thru':row[25], 
                                 'closed':row[26], 
                                 'id':row[2]})
    return airport_list


def get_nfdc_airport_list():
    """Read NFDC airport list and return: Country, State, Airport name, Lat, Lon, Operational"""
    airport_list = []
    i = 0
    with open('APT.txt', 'rb') as aptfile:
        line = aptfile.readline()
        while len(line)>0:
            try:
                if line[0:3] == 'APT':
                    i = i + 1
                    #print(i)
                    latsec = line[538:550].strip()
                    lonsec = line[565:577].strip()
                    NS = 1
                    if latsec[-1] == 'S':
                        NS = -1
                    EW = 1
                    if lonsec[-1] == 'W':
                        EW = -1
                    airport_list.append({'airport':line[133:183].strip(), 
                                         'lat':NS*float(latsec[0:-1])/3600, 
                                         'lon':EW*float(lonsec[0:-1])/3600, 
                                         'link':'nfdc',
                                         'state':line[48:50].strip(), 
                                         'city':line[93:133].strip(),
                                         'start':line[31:41].strip(),
                                         'id':line[27:31].strip()})
                line = aptfile.readline()
                """
                airport = dict()
                airport["RECORD TYPE INDICATOR"] = line[0:3].strip()
                airport["LANDING FACILITY SITE NUMBER"] = line[3:14].strip()
                airport["LANDING FACILITY TYPE"] = line[14:27].strip()
                airport["LOCATION IDENTIFIER"] = line[27:31].strip()
                airport["INFORMATION EFFECTIVE DATE (MM/DD/YYYY)"] = line[31:41].strip()
                airport["FAA REGION CODE"] = line[41:44].strip()
                airport["FAA DISTRICT OR FIELD OFFICE CODE"] = line[44:48].strip()
                airport["ASSOCIATED STATE POST OFFICE CODE"] = line[48:50].strip()
                airport["ASSOCIATED STATE NAME"] = line[50:70].strip()
                airport["ASSOCIATED COUNTY (OR PARISH) NAME"] = line[70:91].strip()
                airport["ASSOCIATED COUNTY'S STATE (POST OFFICE CODE)"] = line[91:93].strip()
                airport["ASSOCIATED CITY NAME"] = line[93:133].strip()
                airport["OFFICIAL FACILITY NAME"] = line[133:183].strip()
                airport["AIRPORT OWNERSHIP TYPE"] = line[183:185].strip()
                airport["FACILITY USE"] = line[185:187].strip()
                airport["FACILITY OWNER'S NAME"] = line[187:222].strip()
                airport["OWNER'S ADDRESS"] = line[222:294].strip()
                airport["OWNER'S CITY, STATE AND ZIP CODE"] = line[294:339].strip()
                airport["FACILITY MANAGER'S NAME"] = line[355:390].strip()
                airport["MANAGER'S ADDRESS"] = line[390:462].strip()
                airport["MANAGER'S CITY, STATE AND ZIP CODE"] = line[462:507].strip()
                airport["AIRPORT REFERENCE POINT LATITUDE (FORMATTED)"] = line[523:538].strip()
                airport["AIRPORT REFERENCE POINT LATITUDE (SECONDS)"] = line[538:550].strip()
                airport["AIRPORT REFERENCE POINT LONGITUDE (FORMATTED)"] = line[550:565].strip()
                airport["AIRPORT REFERENCE POINT LONGITUDE (SECONDS)"] = line[565:577].strip()
                airport["AIRPORT REFERENCE POINT DETERMINATION METHOD"] = line[577:578].strip()
                airport["AIRPORT ELEVATION DETERMINATION METHOD"] = line[585:586].strip()
                airport["MAGNETIC VARIATION AND DIRECTION"] = line[586:589].strip()
                airport["MAGNETIC VARIATION EPOCH YEAR"] = line[589:593].strip()
                airport["AERONAUTICAL SECTIONAL CHART ON WHICH FACILITY"] = line[597:627].strip()
                airport["DISTANCE FROM CENTRAL BUSINESS DISTRICT OF"] = line[627:629].strip()
                airport["DIRECTION OF AIRPORT FROM CENTRAL BUSINESS"] = line[629:632].strip()
                airport["BOUNDARY ARTCC IDENTIFIER"] = line[637:641].strip()
                airport["BOUNDARY ARTCC (FAA) COMPUTER IDENTIFIER"] = line[641:644].strip()
                airport["BOUNDARY ARTCC NAME"] = line[644:674].strip()
                airport["RESPONSIBLE ARTCC IDENTIFIER"] = line[674:678].strip()
                airport["RESPONSIBLE ARTCC (FAA) COMPUTER IDENTIFIER"] = line[678:681].strip()
                airport["RESPONSIBLE ARTCC NAME"] = line[681:711].strip()
                airport["TIE-IN FSS PHYSICALLY LOCATED ON FACILITY"] = line[711:712].strip()
                airport["TIE-IN FLIGHT SERVICE STATION (FSS) IDENTIFIER"] = line[712:716].strip()
                airport["TIE-IN FSS NAME"] = line[716:746].strip()
                airport["LOCAL PHONE NUMBER FROM AIRPORT TO FSS"] = line[746:762].strip()
                airport["TOLL FREE PHONE NUMBER FROM AIRPORT TO FSS"] = line[762:778].strip()
                airport["ALTERNATE FSS IDENTIFIER"] = line[778:782].strip()
                airport["ALTERNATE FSS NAME"] = line[782:812].strip()
                airport["TOLL FREE PHONE NUMBER FROM AIRPORT TO"] = line[812:828].strip()
                airport["IDENTIFIER OF THE FACILITY RESPONSIBLE FOR"] = line[828:832].strip()
                airport["AVAILABILITY OF NOTAM 'D' SERVICE AT AIRPORT"] = line[832:833].strip()
                airport["AIRPORT ACTIVATION DATE (MM/YYYY)"] = line[833:840].strip()
                airport["AIRPORT STATUS CODE"] = line[840:842].strip()
                airport["AIRPORT ARFF CERTIFICATION TYPE AND DATE"] = line[842:857].strip()
                airport["NPIAS/FEDERAL AGREEMENTS CODE"] = line[857:864].strip()
                airport["AIRPORT AIRSPACE ANALYSIS DETERMINATION"] = line[864:877].strip()
                airport["FACILITY HAS BEEN DESIGNATED BY THE U.S. TREASURY"] = line[877:878].strip()
                airport["FACILITY HAS BEEN DESIGNATED BY THE U.S. TREASURY"] = line[878:879].strip()
                airport["FACILITY HAS MILITARY/CIVIL JOINT USE AGREEMENT"] = line[879:880].strip()
                airport["AIRPORT HAS ENTERED INTO AN AGREEMENT THAT"] = line[880:881].strip()
                airport["AIRPORT INSPECTION METHOD"] = line[881:883].strip()
                airport["AGENCY/GROUP PERFORMING PHYSICAL INSPECTION"] = line[883:884].strip()
                airport["LAST PHYSICAL INSPECTION DATE (MMDDYYYY)"] = line[884:892].strip()
                airport["LAST DATE INFORMATION REQUEST WAS COMPLETED"] = line[892:900].strip()
                airport["FUEL TYPES AVAILABLE FOR PUBLIC USE AT THE"] = line[900:940].strip()
                airport["AIRFRAME REPAIR SERVICE AVAILABILITY/TYPE"] = line[940:945].strip()
                airport["POWER PLANT (ENGINE) REPAIR AVAILABILITY/TYPE"] = line[945:950].strip()
                airport["TYPE OF BOTTLED OXYGEN AVAILABLE (VALUE REPRESENTS"] = line[950:958].strip()
                airport["TYPE OF BULK OXYGEN AVAILABLE (VALUE REPRESENTS"] = line[958:966].strip()
                airport["AIRPORT LIGHTING SCHEDULE"] = line[966:973].strip()
                airport["BEACON LIGHTING SCHEDULE"] = line[973:980].strip()
                airport["AIR TRAFFIC CONTROL TOWER LOCATED ON AIRPORT"] = line[980:981].strip()
                airport["UNICOM FREQUENCY AVAILABLE AT THE AIRPORT"] = line[981:988].strip()
                airport["COMMON TRAFFIC ADVISORY FREQUENCY (CTAF)"] = line[988:995].strip()
                airport["SEGMENTED CIRCLE AIRPORT MARKER SYSTEM ON THE AIRPORT"] = line[995:999].strip()
                airport["LENS COLOR OF OPERABLE BEACON LOCATED ON THE AIRPORT"] = line[999:1002].strip()
                airport["LANDING FEE CHARGED TO NON-COMMERCIAL USERS OF"] = line[1002:1003].strip()
                airport['A "Y" IN THIS FIELD INDICATES THAT THE LANDING'] = line[1003:1004].strip()
                airport["12-MONTH ENDING DATE ON WHICH ANNUAL OPERATIONS DATA"] = line[1061:1071].strip()
                airport["AIRPORT POSITION SOURCE"] = line[1071:1087].strip()
                airport["AIRPORT POSITION SOURCE DATE (MM/DD/YYYY)"] = line[1087:1097].strip()
                airport["AIRPORT ELEVATION SOURCE"] = line[1097:1113].strip()
                airport["AIRPORT ELEVATION SOURCE DATE (MM/DD/YYYY)"] = line[1113:1123].strip()
                airport["CONTRACT FUEL AVAILABLE"] = line[1123:1124].strip()
                airport["TRANSIENT STORAGE FACILITIES"] = line[1124:1136].strip()
                airport["OTHER AIRPORT SERVICES AVAILABLE"] = line[1136:1207].strip()
                airport["WIND INDICATOR"] = line[1207:1210].strip()
                airport["ICAO IDENTIFIER"] = line[1210:1217].strip()
                airport["AIRPORT RECORD FILLER (BLANK)"] = line[1217:1529].strip()
                """

            except:
                """This is a dumb solution."""
                print(line)
                break
    print(i)
    return airport_list
    

def get_lat_lon_from_list(airports):
    lat = [float(airport.get('lat')) for airport in airports]
    lon = [float(airport.get('lon')) for airport in airports]
    return lat,lon


def main():
    print('Scraping... %s' % datetime.datetime.now().time())
    scrape_airports()
    print('Reading... %s' % datetime.datetime.now().time())
    airports = read_airport_files()
    print('Writing csv... %s' % datetime.datetime.now().time())
    write_csv_file(airports)
    print('Writing kml... %s' % datetime.datetime.now().time())
    write_kml_file(airports)
    print('Reading BTS... %s' % datetime.datetime.now().time())
    
    bts_airports = get_bts_airport_list()
    #pp = pprint.PrettyPrinter(indent=4)
    #pp.pprint(bts_airports)
    print('Reading NFDC... %s' % datetime.datetime.now().time())
    nfdc_airports = get_nfdc_airport_list()
    #print(nfdc_airports)
    print('Finishing... %s' % datetime.datetime.now().time())
    
    print('{} website airports parsed.'.format(len(airports)))
    print('{} bts airports parsed.'.format(len(bts_airports)))
    print('{} nfdc airports parsed.'.format(len(nfdc_airports)))
    
    potential_missing_facilities = compare_locations(nfdc_airports,bts_airports)
    compare_locations(airports,potential_missing_facilities)
    #TODO: Check if open airports exist in the same location as the closed results
    pass

if __name__ == '__main__':
    main()
