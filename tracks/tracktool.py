#!/usr/bin/env python3

import sys
import glob
import xml.etree.ElementTree as ET
import datetime as DT

COMBINED_TRACKS_FILE = 'James_RTUK23_Tracks.gpx'

LEG_FILTER = (
  ('Gosport to Dover',              ('2023-04-22 15:11:49', '2023-04-23 10:47:49')),
  ('Dover to Ramsgate',             ('2023-04-25 14:59:49', '2023-04-25 18:44:54')),
  ('Ramsgate to Harwich',           ('2023-04-26 05:50:21', '2023-04-26 16:58:53')),
  ('Harwich to Woodbridge',         ('2023-04-27 13:14:04', '2023-04-27 17:05:39')),
  ('Woodbridge to Lowestoft',       ('2023-04-30 07:34:46', '2023-04-30 16:41:02')),
  ('Lowestoft to Scarborough',      ('2023-05-03 10:39:57', '2023-05-04 09:30:06')),
  ('Scarborough to Tyne',           ('2023-05-08 05:50:57', '2023-05-08 23:35:11')),
  ('Tyne to Blyth',                 ('2023-05-13 12:55:25', '2023-05-13 15:43:06')),
  ('Blyth to Newton Haven ⚓',      ('2023-05-15 09:58:32', '2023-05-15 19:34:58')),
  ('Newton Haven ⚓ to Eyemouth',   ('2023-05-16 09:19:34', '2023-05-16 19:09:29',
                                     '2023-05-16 20:18:33', '2023-05-16 20:47:24')),
  ('Eyemouth to Arbroath',          ('2023-05-18 04:08:11', '2023-05-18 12:12:59')),
  ('Arbroath to Peterhead',         ('2023-05-20 12:38:18', '2023-05-21 03:26:31')),
  ('Peterhead to Wick',             ('2023-05-25 06:44:48', '2023-05-26 05:30:07')),
)

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

def usage(exec_name):
  print("""Usage:

Combine all tracks from multiple raw GPX files into single track in single GPX file:
  {0} cs combined.gpx raw_garmin73/*.gpx

Combine all tracks and then split again according to LEG_FILTER into single GPX file:
  {0} cf combined.gpx raw_garmin73/*.gpx

Same as above but use \"{1}\" as output filename:
  {0} cfd raw_garmin73/*.gpx

Combine all tracks and export only those that occur since LEG_FILTER:
  {0} cn newtracks.gpx raw_garmin73/*.gpx
""".format(exec_name, COMBINED_TRACKS_FILE), file=sys.stderr)
  sys.exit(-1)

def main(argv):
  ex = argv[0]

  if len(argv) == 1:
    usage(ex)
  
  cmd = argv[1]
  args = argv[2:]
  nargs = len(args)

  ok = False

  if cmd == 'cs':
    if nargs < 2:
      usage(ex)
    
    track = parse_all_tracks(args[1:])
    if track is not False:
      ok = write_tracks({"Combined": track}, args[0])
  
  else:
    usage(ex)
  
  if not ok:
    print("Abortin'", file=sys.stderr)
    return -1

  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))

