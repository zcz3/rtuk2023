
import sys
import csv
import pprint
import datetime

from tracktool import oh, read_tracklog, expand_globs, combine_trkpts, MODES_STATIC, MODES_MOVING



def calc_nm(pt1, pt2):
  from geopy import distance

  d1 = (float(pt1['lat']), float(pt1['lon']))
  d2 = (float(pt2['lat']), float(pt2['lon']))

  return distance.distance(d1, d2).nautical


# Goes through all trkpts and calculates cumulative distance between each
def calc_points_nm(points):
  last = None
  nm = 0.0

  for pt in points:
    if last is not None:
      nm += calc_nm(last, pt)
    
    pt['nm'] = nm
    last = pt


# Returns (first trkpt before, closest trkpt, first trkpt after)
# trkpt must be within 5mins
def match_trkpt(time, points, thresh_mins=20):
  before = None
  after = None
  last = None

  for pt in points:
    if pt['ptime'] > time:
      after = pt
      before = last
      break
    
    last = pt
  
  thresh = datetime.timedelta(minutes=thresh_mins)
  if before and (time - before['ptime']) > thresh:
    before = None
  if after and (after['ptime'] - time) > thresh:
    after = None
  
  close = None

  if before and after:
    if (time - before['ptime']) < (after['ptime'] - time):
      close = before
    else:
      close = after
  
  return (before, close, after)



def format_td(td):
  return str(td)



def main(argv):
  out_path = argv[1]
  tracklog_path = argv[2]
  gpx_files = expand_globs(argv[3:])

  legs = read_tracklog(tracklog_path)
  print('Num legs: %d' % len(legs))

  ok, res = combine_trkpts(gpx_files)
  if not ok:
    oh(res)

  pts = res
  print('Num unique trkpts: %d' % len(pts))

  print("Calculating distances")
  calc_points_nm(pts)
  print("Done (%d)" % pts[-1]['nm'])

  for leg in legs:
    last_mode = None

    for t in leg['tracks']:
      (before, close, after) = match_trkpt(t['date'], pts)
      pt = None
      mode = None
      if t['mode'] in MODES_STATIC:
        mode = 'Static'
      if t['mode'] in MODES_MOVING:
        mode = 'Dynamic'
      
      if mode == 'Static':
        if last_mode == 'Dynamic':
          pt = before
          if not pt:
            oh("Could not find trkpt before "+ t['date'].isoformat())
      
      elif mode == 'Dynamic':
        if last_mode == 'Static' or last_mode is None:
          pt = after
          if not pt:
            oh("Could not find trkpt after " + t['date'].isoformat())
        
        if last_mode == 'Dynamic':
          pt = close
          if not pt:
            oh("Could not find trkpt")
      
      else:
        oh("Invalid mode")
      
      t['trkpt'] = pt

      last_mode = mode


  # Process stats

  mtotal = {
    'All': datetime.timedelta(0),
    'Engine': datetime.timedelta(0),
    'Sail': datetime.timedelta(0),
    'MotorSail': datetime.timedelta(0),
  }

  Dtotal = {
    'All': 0.0,
    'Engine': 0.0,
    'Sail': 0.0,
    'MotorSail': 0.0,
  }

  for leg in legs:

    leg['mtotal'] = {
      'All': datetime.timedelta(0),
      'Engine': datetime.timedelta(0),
      'Sail': datetime.timedelta(0),
      'MotorSail': datetime.timedelta(0),
    }

    leg['Dtotal'] = {
      'All': 0.0,
      'Engine': 0.0,
      'Sail': 0.0,
      'MotorSail': 0.0,
    }

    last = None

    for t in leg['tracks']:

      if last and last['mode'] in MODES_MOVING:
        elap = t['date'] - last['date']
        m = last['mode']
        mtotal['All'] += elap
        mtotal[m] += elap
        leg['mtotal']['All'] += elap
        leg['mtotal'][m] += elap

        nm = t['trkpt']['nm'] - last['trkpt']['nm']
        Dtotal['All'] += nm
        Dtotal[m] += nm
        leg['Dtotal']['All'] += nm
        leg['Dtotal'][m] += nm

      
      last = t


  mtotal['Check'] = mtotal['Engine'] + mtotal['Sail'] + mtotal['MotorSail']


  # Write stats

  with open(out_path, 'w') as f:
    out = csv.writer(f, delimiter=',', quoting=csv.QUOTE_NONNUMERIC)

    out.writerow((
      'Leg',
      'Stopover type',
      'Total Time',
      'Total Distance (nm)',
      'Sailing Time',
      'Sailing Distance (nm)',
      'Engine Time',
      'Engine Distance (nm)',
      'Motorsail Time',
      'Motorsail Distance (nm)',
      'Average Speed (knots)',
    ))

    all_td = mtotal['All']
    all_tnm = Dtotal['All']
    row = ['TOTAL TRIP', '', ]
    row.append(format_td(all_td))
    row.append(int(all_tnm))

    for n in ('Sail', 'Engine', 'MotorSail'):
      td = mtotal[n]
      dperc = (td.total_seconds() / all_td.total_seconds()) * 100
      row.append("{0} ({1}%)".format(format_td(td), round(dperc)))

      tnm = Dtotal[n]
      nmperc = (tnm / all_tnm) * 100
      row.append("{0} ({1}%)".format(int(tnm), round(nmperc)))
    
    row.append(all_tnm / (all_td.total_seconds() / 3600.0))

    out.writerow(row)

    for l in legs:
      all_td = l['mtotal']['All']
      all_tnm = l['Dtotal']['All']
      row = ['{0} to {1}'.format(l['start'], l['stop']), l['tracks'][-1]['mode']]
      row.append(format_td(all_td))
      row.append(int(all_tnm))

      for n in ('Sail', 'Engine', 'MotorSail'):
        td = l['mtotal'][n]
        dperc = (td.total_seconds() / all_td.total_seconds()) * 100
        row.append("{0} ({1}%)".format(format_td(td), round(dperc)))

        tnm = l['Dtotal'][n]
        nmperc = (tnm / all_tnm) * 100
        row.append("{0} ({1}%)".format(int(tnm), round(nmperc)))
      
      row.append(all_tnm / (all_td.total_seconds() / 3600.0))

      out.writerow(row)

  #pprint.pprint(legs)

  return 0



if __name__ == "__main__":
  sys.exit(main(sys.argv))

