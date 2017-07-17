# -*- coding: utf-8 -*-
"""
Created on Fri Aug 21 06:34:14 2015

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
                    response     = urllib2.urlopen(this_deep_link)
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

    for item in items:
        if recorded_states and item.get('state') not in recorded_states:
            kml_output_file.write('</Folder>\n')
            
            kml_state_output_file.write('</Folder>\n')
            kml_state_output_file.write('</Document></kml>')
            kml_state_output_file.close()
        if item.get('state') not in recorded_states:
            kml_output_file.write('<Folder><name>{}</name><open>0</open>\n'.format(item.get('state')))
            recorded_states[item.get('state')] = 1
    
            kml_state_output_file = open('./{}_{}.kml'.format(base_name,item.get('state')),'w')
            kml_state_output_file.write(kml_head)
            kml_state_output_file.write('<Folder><name>{}</name><open>0</open>\n'.format(item.get('state')))
        else:
            recorded_states[item.get('state')] = recorded_states[item.get('state')] + 1
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
        if closest > filter_dist and test_airport.get('closed') == '1':
            missing_items.append({'airport':"{} ({})".format(test_airport.get('airport'),test_airport.get('id')), 
                                  'lat':test_airport.get('lat'), 
                                  'lon':test_airport.get('lon'), 
                                  'state':test_airport.get('state'), 
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
    write_kml_file(missing_items,base_name='missing_items')

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
        for row in [row for row in bts_airports if row[27] == '1' and row[7] == 'US' and '.' in row[18]]:
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
    return []
    

def get_lat_lon_from_list(airports):
    lat = [float(airport.get('lat')) for airport in airports]
    lon = [float(airport.get('lon')) for airport in airports]
    return lat,lon


def main():
    scrape_airports()
    airports = read_airport_files()
    write_csv_file(airports)
    write_kml_file(airports)
    
    bts_airports = get_bts_airport_list()
    #pp = pprint.PrettyPrinter(indent=4)
    #pp.pprint(bts_airports)
    
    print('{} website airports parsed.'.format(len(airports)))
    print('{} bts airports parsed.'.format(len(bts_airports)))
    
    compare_locations(airports,bts_airports)
    #TODO: Check if open airports exist in the same location as the closed results
    pass

if __name__ == '__main__':
    main()
