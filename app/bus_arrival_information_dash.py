# version 6: select only recent half minute's signals to process
'''
set the speed of bus with 10 m/s
set the maximum distance you want to walk 
    for a nearby stop is ~100 m
'''
SPEED = 10.0
MAX_WALK_LENGTH = 100.0


import psycopg2
import datetime
import time
import pandas as pd
import math

from confidential_app import get_confidential


def get_stop_name(stop_id):
    '''
    @input (string): stop id
    @output (string): information about the stop name
    '''
    if len(stop_id) != 6 or not unicode(stop_id, 'utf-8').isnumeric():
        return "The stop ID you type is incorrect. Please type a 6-digit number!"
    
    database_password = get_confidential('database_password')
    database_host = get_confidential('database_host')
    conn = psycopg2.connect(database = "test", 
                            user = "postgres", 
                            password = database_password, 
                            host = database_host, 
                            port = "5432")
    cur = conn.cursor()
    cur.execute('''
    SELECT * FROM STOP_INFORMATION WHERE STOP_ID = '%s';
    ''' % stop_id)
    temp = cur.fetchall()
    if len(temp) == 0:
        return 'The stop id could not be found'
    return temp[0][1]
    
    
def get_arrival_information_for_stop(stop_id):
    '''
    @input (string): stop id you want to get information about
    @output (string): arrival information for this stop
    @function: this function is to calculate the arrival information
        for a bus stop. the steps are:
        1. select all the schedule information for this stop
        2. select data of recent 1 minute, for same trip, keep the most
            recent one
        3. inner join these two parts on trip id, after doing that, the
            result only has signals related to this stop
        4. process each related signals to get the arrival information
            and put them together
    '''
    
    database_password = get_confidential('database_password')
    database_host = get_confidential('database_host')
    conn = psycopg2.connect(database = "test", 
                            user = "postgres", 
                            password = database_password, 
                            host = database_host, 
                            port = "5432")
    cur = conn.cursor()
    
    # step 1
    cur.execute('''
    DROP TABLE IF EXISTS RELATED_TRIP;
    SELECT * INTO RELATED_TRIP
    FROM SCHEDULE_INFORMATION WHERE STOP_ID = '%s';
    ''' % stop_id)
    
    # step 2
    half_minute_ago = datetime.datetime.now() - datetime.timedelta(0, 30, 0)
    cur.execute('''DROP TABLE IF EXISTS RECENT_RECORD;
                   SELECT * INTO RECENT_RECORD 
                   FROM RECORD 
                   WHERE TIME_STAMP >= TIMESTAMP'%s';
                '''% half_minute_ago)
    conn.commit()
    
    # step 3
    cur.execute('''
    SELECT RECENT_RECORD.*, RELATED_TRIP.SCHEDULED_TIME, RELATED_TRIP.STOP_ID
    FROM RELATED_TRIP
    INNER JOIN
    RECENT_RECORD
    ON RELATED_TRIP.TRIP_ID = RECENT_RECORD.TRIP_ID;
    ''')
    
    # step 4
    
    # each row contains information for one upcoming bus
    rows = cur.fetchall()
    schedule_list = []
    for row in rows:
        # get the schedule time to the next stop:
        cur.execute("SELECT SCHEDULED_TIME FROM SCHEDULE_INFORMATION WHERE TRIP_ID = %s AND STOP_ID = %s"
                    , (row[2], row[4]))
        
        scheduled_time_from_beginning_to_next_stop = cur.fetchall()[0][0]
        scheduled_time_from_beginning_to_the_stop = float(row[5])
        
        # if the next stop is already passing the stop we want to look into, then don't need to process
        if scheduled_time_from_beginning_to_the_stop < scheduled_time_from_beginning_to_next_stop:
            continue
        # calculated the arrival time
        arrival_time_for_this_route = int(scheduled_time_from_beginning_to_the_stop - \
                                    scheduled_time_from_beginning_to_next_stop + \
                                    row[3] / SPEED / 60)
        schedule_list.append("The next " + row[1] + " is arriving in " \
                             + str(arrival_time_for_this_route) + ' min')
    
    conn.close()
    # if no signal processed, it means no bus arriving
    if len(schedule_list) == 0:
        return "Currently there is no bus arriving!"
    # join them with '\n', this is for DASH application
    else:
        return '***'.join(schedule_list)

def find_nearby_stops(stop_id, length = MAX_WALK_LENGTH):
    '''
    @input
    find all the stops within a square that the current stop is the center
    and the side of the square is 2 x length
    '''
    database_password = get_confidential('database_password')
    database_host = get_confidential('database_host')
    conn = psycopg2.connect(database = "test", 
                            user = "postgres", 
                            password = database_password, 
                            host = database_host, 
                            port = "5432")
    cur = conn.cursor()
    cur.execute("SELECT STOP_LAT, STOP_LON FROM STOP_INFORMATION WHERE STOP_ID = '%s';" %stop_id)
    temp = cur.fetchall()
    # exception handling
    if not temp:
        print("The stop id cannot be found!")
        return []
    
    # 1 degree latitude = 1.11e5 meters
    # 1 degree longitude = 1.11e5 * cos latitude meters
    latitude, longitude = temp[0]
    delta_latitude = length / 1.11e5
    delta_longitude = length / (1.11e5 * math.cos(math.radians(latitude)))
    latitude_interval_left, latitude_interval_right = \
                                latitude - delta_latitude, latitude + delta_latitude
    longitude_interval_left, longitude_interval_right = \
                                longitude - delta_longitude, longitude + delta_longitude
    
    #print(latitude_interval_left, latitude_interval_right)
    #print(longitude_interval_left, longitude_interval_right)
    
    cur.execute('''
    SELECT STOP_ID, STOP_NAME 
    FROM STOP_INFORMATION 
    WHERE STOP_LAT > %s AND STOP_LAT < %s AND STOP_LON > %s AND STOP_LON < %s
    ''', (latitude_interval_left, latitude_interval_right, 
         longitude_interval_left, longitude_interval_right))
    
    nearby_stops = []
    temp = cur.fetchall()
    for nearby_stop_id in temp:
        if nearby_stop_id[0] == stop_id:
            continue
        nearby_stops.append(nearby_stop_id[0])
    conn.close()
    return nearby_stops

def combine_nearby_stop_information(stop_id):
    nearby_stops = find_nearby_stops(stop_id)
    if len(nearby_stops) == 0:
        return ''
    ans = []
    for stop in nearby_stops:
        ans.append('Information for stop ' + stop + ': ' + get_arrival_information_for_stop(stop))
    return '################'.join(ans)
