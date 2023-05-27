#!/usr/bin/env python3

import sys
import glob
import xml.etree.ElementTree as ET


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

  write_track(points, 'test.gpx')
  
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

  try:
    lat = pt.attrib['lat']
    lon = pt.attrib['lon']
  except KeyError:
    return False
  
  timetag = pt.find('./{*}time')
  if timetag is None or timetag.text is None:
    return False

  time = timetag.text

  if len(time) == 0 or len(lat) == 0 or len(lon) == 0:
    return False
  
  return {
    'time': time,
    'lat': lat,
    'lon': lon,
  }

def write_track(points, gpx_name):
  root = ET.Element('gpx')
  trk = ET.SubElement(root, 'trk')
  name = ET.SubElement(trk, 'name')
  name.text = 'My Fancy Track'
  seg = ET.SubElement(trk, 'trkseg')

  for ptk in points:
    pt = points[ptk]

    trkpt = ET.SubElement(seg, 'trkpt')
    trkpt.attrib['lat'] = pt['lat']
    trkpt.attrib['lon'] = pt['lon']
    time = ET.SubElement(trkpt, 'time')
    time.text = pt['time']
  
  with open(gpx_name, 'wt') as f:
    f.write(ET.tostring(root).decode())

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

