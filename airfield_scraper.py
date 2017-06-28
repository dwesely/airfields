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

base_url = "http://www.airfields-freeman.com/"    

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
    total_downloaded = 0
    response  = urllib2.urlopen(base_url)
    home_page = response.read()
    total_downloaded = total_downloaded + len(home_page)
    links     = re.findall('HREF="([^.]+).htm"',home_page)
    print(links)
    home_soup = BeautifulSoup(home_page, 'html.parser')
    state_cells = home_soup.find_all('td')
    #check this state for updates
    for state_cell in state_cells:
        #print(state_cell)
        deep_link = get_link_from_html(repr(state_cell))
        state,state_file = deep_link.split('/')
        
        update_date = get_mdyyyy_from_text(repr(state_cell))
        
        local_date = get_latest_file(state_file.replace('.htm','*.htm'))

        print('{} last updated {}, local version updated {}'.format(deep_link,update_date,local_date))
        
        if update_date > local_date:
            this_link  = '{}{}'.format(base_url,deep_link)
            response   = urllib2.urlopen(this_link)
            state_page = response.read()
            total_downloaded = total_downloaded + len(state_page)
            
            state_soup = BeautifulSoup(state_page, 'html.parser')
            region_cells = state_soup.find_all('td')
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


def read_airport_files():
    """Parse the downloaded airport files and save details"""
    #TODO: Speed this up, assemble the strings and write all at once
    leaflet_output_file = open('./leaflet_code.txt','w')
    kml_output_file = open('./abandoned_airports.kml','w')
    csv_output_file = open('./abandoned_airports.csv','w')
    csv_head = 'State,Airport,Lat,Lon,Link\n'
    csv_output_file.write(csv_head)
    kml_head = '''<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
<Document><name>abandoned_airports.kml</name>
	<Style id="sh_airports"><IconStyle><scale>1.4</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/airports.png</href></Icon><hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/></IconStyle><ListStyle></ListStyle></Style>
	<Style id="sn_airports"><IconStyle><scale>1.2</scale><Icon><href>http://maps.google.com/mapfiles/kml/shapes/airports.png</href></Icon><hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/></IconStyle><ListStyle></ListStyle></Style>
	<StyleMap id="msn_airports"><Pair><key>normal</key><styleUrl>#sn_airports</styleUrl></Pair><Pair><key>highlight</key><styleUrl>#sh_airports</styleUrl></Pair></StyleMap>
  '''
    kml_output_file.write(kml_head)
    
    recorded_states = set()
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
            airports = re.findall(r'__\s+([^(_]+)\s+(-?\d+.\d+), (-?\d+.\d+)',repr(trimmed_text))
            state = re.findall(r'Airfields_([A-Z]+)_',thisFilename)
            state = state[0]
            link = '{}{}/{}'.format(base_url,state,thisFilename)
            if recorded_states and state not in recorded_states:
                kml_output_file.write('</Folder>\n')
                
                kml_state_output_file.write('</Folder>\n')
                kml_state_output_file.write('</Document></kml>')
                kml_state_output_file.close()
                
            if state not in recorded_states:
                kml_output_file.write('<Folder><name>{}</name><open>0</open>\n'.format(state))
                recorded_states.add(state)

                kml_state_output_file = open('./abandoned_airports_{}.kml'.format(state),'w')
                kml_state_output_file.write(kml_head)
                kml_state_output_file.write('<Folder><name>{}</name><open>0</open>\n'.format(state))
            
            for airport,lat,lon in airports:
                leaflet_output_file.write("L.marker([{}, {}]).addTo(map)\n    .bindPopup('<a href=\"{}\">{}</a>')\n    .openPopup();\n".format(lat,lon,link,airport))
                placemark = '<Placemark><name>{}</name><description><![CDATA[<a href="{}">{}</a>]]></description><styleUrl>#msn_airports</styleUrl><Point><gx:drawOrder>1</gx:drawOrder><coordinates>{},{},0</coordinates></Point></Placemark>\n'.format(airport.replace('&',' and '),link,'Link',lon,lat)
                kml_output_file.write(placemark)
                kml_state_output_file.write(placemark)
                csv_output_file.write('"{}","{}",{},{},"{}"\n'.format(state,airport,lat,lon,link))
            pass
    kml_output_file.write('</Folder>\n')
    kml_output_file.write('</Document></kml>')

    leaflet_output_file.close()
    kml_output_file.close()
    csv_output_file.close()


def compare_locations():
    """Check Abandoned Airfields locations against BTS and NFDC airport locations"""


def get_bts_airport_list():
    """Read BTS Master Coordinates list and return: Country, State, Airport name, Lat, Lon, Operational"""
    return []


def get_nfdc_airport_list():
    """Read NFDC airport list and return: Country, State, Airport name, Lat, Lon, Operational"""
    return []


def main():
    scrape_airports()
    read_airport_files()
    get_bts_airport_list()
    compare_locations()
    pass

if __name__ == '__main__':
    main()