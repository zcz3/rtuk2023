#!/usr/bin/env python3

import sys
import glob
import xml.etree.ElementTree as ET


COMBINED_TRACKS_FILE = 'James_RTUK23_Tracks.gpx'



def parse_all_tracks(glob_list):
  files = []
  for g in glob_list:
    files += glob.glob(g)
  
  if not len(files):
    print('No GPS files found')
    return False

  print('Parsing %d GPS files' % len(files))

  points = {}

  for f in files:
    if parse_tracks(f, points) is False:
      print('Aborting')
      return False
  
  print('Total %d points' % len(points))

  write_track(points, COMBINED_TRACKS_FILE)
  
  return True

def parse_tracks(gpx_file, points):
  print(gpx_file)

  try:
    et = ET.parse(gpx_file)
  except FileNotFoundError:
    print('  File not found')
    return False
  except ET.ParseError:
    print('  Parse error')
    return False

  # gpx -> trk -> trkseg -> trkpt
  
  rootname = et.getroot().tag
  if len(rootname) < 3 or rootname[-3:] != 'gpx':
    print('  Parse error')
    return False
  
  trks = et.findall('./{*}trk')
  print('  %d tracks' % len(trks))

  num_prev_points = len(points)
  num_points = 0
  
  for trk in trks:
    for pt in trk.findall('.//{*}trkpt'):
      point = parse_trkpt(pt)

      if point is False:
        print('  Could not parse trkpt')
        return False
      
      points[point['time']] = point
      num_points += 1
  
  print('  %d points (%d unique)' % (num_points, len(points) - num_prev_points))

  return True

def parse_trkpt(pt):
  # We keep these as text to preserve accuracy
  time = ''
  lat = ''
  lon = ''
  ele = ''

  try:
    lat = pt.attrib['lat']
    lon = pt.attrib['lon']
  except KeyError:
    return False
  
  timetag = pt.find('./{*}time')
  if timetag is None or timetag.text is None:
    return False

  time = timetag.text

  eletag = pt.find('./{*}ele')
  if eletag is None or eletag.text is None:
    return False

  ele = eletag.text

  if len(time) == 0 or len(lat) == 0 or len(lon) == 0 or len(ele) == 0:
    return False
  
  return {
    'time': time,
    'lat': lat,
    'lon': lon,
    'ele': ele,
  }

def write_track(points, gpx_name):
  GPX_NS = 'http://www.topografix.com/GPX/1/1'
  NSP = '{%s}' % GPX_NS
  ET.register_namespace('', GPX_NS)

  root = ET.Element(NSP + 'gpx')
  root.attrib['version'] = '1.1'
  root.attrib['creator'] = 'https://github.com/zcz3/rtuk2023'

  trk = ET.SubElement(root, NSP + 'trk')
  name = ET.SubElement(trk, NSP + 'name')
  name.text = 'My Fancy Track'
  seg = ET.SubElement(trk, NSP + 'trkseg')

  for ptk in points:
    pt = points[ptk]

    trkpt = ET.SubElement(seg, NSP + 'trkpt')
    trkpt.attrib['lat'] = pt['lat']
    trkpt.attrib['lon'] = pt['lon']
    time = ET.SubElement(trkpt, NSP + 'time')
    time.text = pt['time']
    ele = ET.SubElement(trkpt, NSP + 'ele')
    ele.text = pt['ele']
  
  tree = ET.ElementTree(root)
  ET.indent(tree)

  tree.write(
    gpx_name,
    encoding='unicode',
    xml_declaration=True)

def main(argv):
  result = False

  if len(argv) > 1:
    result = parse_all_tracks(argv[1:])
  else:
    print('Specify list of GPX files')
  
  if result:
    return 0
  return -1

if __name__ == "__main__":
  sys.exit(main(sys.argv))

