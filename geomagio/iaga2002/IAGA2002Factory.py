"""Factory that loads IAGA2002 Files."""

import obspy.core
import os
import urllib2
from .. import ChannelConverter
from ..TimeseriesFactory import TimeseriesFactory
from ..TimeseriesFactoryException import TimeseriesFactoryException
from IAGA2002Parser import IAGA2002Parser
from IAGA2002Writer import IAGA2002Writer


# pattern for iaga 2002 file names
IAGA_FILE_PATTERN = '%(obs)s%(ymd)s%(t)s%(i)s.%(i)s'


def read_url(url):
    """Open and read url contents.

    Parameters
    ----------
    url : str
        A urllib2 compatible url, such as http:// or file://.

    Returns
    -------
    str
        contents returned by url.

    Raises
    ------
    urllib2.URLError
        if any occurs
    """
    response = urllib2.urlopen(url)
    content = None
    try:
        content = response.read()
    except urllib2.URLError, e:
        print e.reason
        raise
    finally:
        response.close()
    return content


class IAGA2002Factory(TimeseriesFactory):
    """TimeseriesFactory for IAGA 2002 formatted files.

    Parameters
    ----------
    urlTemplate : str
        A string that contains any of the following replacement patterns:
        - '%(i)s' : interval abbreviation
        - '%(interval)s' interval name
        - '%(obs)s' lowercase observatory code
        - '%(OBS)s' uppercase observatory code
        - '%(t)s' type abbreviation
        - '%(type)s' type name
        - '%(ymd)s' time formatted as YYYYMMDD

    See Also
    --------
    IAGA2002Parser
    """

    def __init__(self, urlTemplate, observatory=None, channels=None, type=None,
            interval=None):
        TimeseriesFactory.__init__(self, observatory, channels, type, interval)
        self.urlTemplate = urlTemplate

    def get_timeseries(self, starttime, endtime, observatory=None,
            channels=None, type=None, interval=None):
        """Get timeseries data

        Parameters
        ----------
        observatory : str
            observatory code.
        starttime : obspy.core.UTCDateTime
            time of first sample.
        endtime : obspy.core.UTCDateTime
            time of last sample.
        type : {'variation', 'quasi-definitive'}
            data type.
        interval : {'minute', 'second'}
            data interval.

        Returns
        -------
        obspy.core.Stream
            timeseries object with requested data.

        Raises
        ------
        TimeseriesFactoryException
            if invalid values are requested, or errors occur while
            retrieving timeseries.
        """
        observatory = observatory or self.observatory
        channels = channels or self.channels
        type = type or self.type
        interval = interval or self.interval
        days = self._get_days(starttime, endtime)
        timeseries = obspy.core.Stream()
        for day in days:
            url = self._get_url(observatory, day, type, interval)
            iagaFile = read_url(url)
            timeseries += self.parse_string(iagaFile)
        # merge channel traces for multiple days
        timeseries.merge()
        # trim to requested start/end time
        timeseries.trim(starttime, endtime)
        return timeseries

    def parse_string(self, iaga2002String):
        """Parse the contents of a string in the format of an IAGA2002 file.

        Parameters
        ----------
        iaga2002String : str
            string containing IAGA2002 content.

        Returns
        -------
        obspy.core.Stream
            parsed data.
        """
        parser = IAGA2002Parser()
        parser.parse(iaga2002String)
        metadata = parser.metadata
        starttime = obspy.core.UTCDateTime(parser.times[0])
        endtime = obspy.core.UTCDateTime(parser.times[-1])
        data = parser.data
        length = len(data[data.keys()[0]])
        rate = (length - 1) / (endtime - starttime)
        stream = obspy.core.Stream()
        for channel in data.keys():
            stats = obspy.core.Stats(metadata)
            stats.starttime = starttime
            stats.sampling_rate = rate
            stats.npts = length
            stats.channel = channel
            if channel == 'D':
                data[channel] = ChannelConverter.get_radians_from_minutes(
                    data[channel])
            stream += obspy.core.Trace(data[channel], stats)
        return stream

    def _get_url(self, observatory, date, type='variation', interval='minute'):
        """Get the url for a specified IAGA2002 file.

        Replaces patterns (described in class docstring) with values based on
        parameter values.

        Parameters
        ----------
        observatory : str
            observatory code.
        date : obspy.core.UTCDateTime
            day to fetch (only year, month, day are used)
        type : {'variation', 'quasi-definitive'}
            data type.
        interval : {'minute', 'second'}
            data interval.

        Raises
        ------
        TimeseriesFactoryException
            if type or interval are not supported.
        """
        return self.urlTemplate % {
                'i': self._get_interval_abbreviation(interval),
                'interval': self._get_interval_name(interval),
                'obs': observatory.lower(),
                'OBS': observatory.upper(),
                't': self._get_type_abbreviation(type),
                'type': self._get_type_name(type),
                'ymd': date.strftime("%Y%m%d")}

    def _get_interval_abbreviation(self, interval):
        """Get abbreviation for a data interval.

        Used by ``_get_url`` to replace ``%(i)s`` in urlTemplate.

        Parameters
        ----------
        interval : {'daily', 'hourly', 'minute', 'monthly', 'second'}

        Returns
        -------
        abbreviation for ``interval``.

        Raises
        ------
        TimeseriesFactoryException
            if ``interval`` is not supported.
        """
        interval_abbr = None
        if interval == 'daily':
            interval_abbr = 'day'
        elif interval == 'hourly':
            interval_abbr = 'hor'
        elif interval == 'minute':
            interval_abbr = 'min'
        elif interval == 'monthly':
            interval_abbr = 'mon'
        elif interval == 'second':
            interval_abbr = 'sec'
        else:
            raise TimeseriesFactoryException(
                    'Unexpected interval "%s"' % interval)
        return interval_abbr

    def _get_interval_name(self, interval):
        """Get name for a data interval.

        Used by ``_get_url`` to replace ``%(interval)s`` in urlTemplate.

        Parameters
        ----------
        interval : {'minute', 'second'}

        Returns
        -------
        name for ``interval``.

        Raises
        ------
        TimeseriesFactoryException
            if ``interval`` is not supported.
        """
        interval_name = None
        if interval == 'minute':
            interval_name = 'OneMinute'
        elif interval == 'second':
            interval_name = 'OneSecond'
        else:
            raise TimeseriesFactoryException(
                    'Unsupported interval "%s"' % interval)
        return interval_name

    def _get_type_abbreviation(self, type):
        """Get abbreviation for a data type.

        Used by ``_get_url`` to replace ``%(t)s`` in urlTemplate.

        Parameters
        ----------
        type : {'definitive', 'provisional', 'quasi-definitive', 'variation'}

        Returns
        -------
        name for ``type``.

        Raises
        ------
        TimeseriesFactoryException
            if ``type`` is not supported.
        """
        type_abbr = None
        if type == 'definitive':
            type_abbr = 'd'
        elif type == 'provisional':
            type_abbr = 'p'
        elif type == 'quasi-definitive':
            type_abbr = 'q'
        elif type == 'variation':
            type_abbr = 'v'
        else:
            raise TimeseriesFactoryException(
                    'Unexpected type "%s"' % type)
        return type_abbr

    def _get_type_name(self, type):
        """Get name for a data type.

        Used by ``_get_url`` to replace ``%(type)s`` in urlTemplate.

        Parameters
        ----------
        type : {'variation', 'quasi-definitive'}

        Returns
        -------
        name for ``type``.

        Raises
        ------
        TimeseriesFactoryException
            if ``type`` is not supported.
        """
        type_name = None
        if type == 'variation':
            type_name = ''
        elif type == 'quasi-definitive':
            type_name = 'QuasiDefinitive'
        else:
            raise TimeseriesFactoryException(
                    'Unsupported type "%s"' % type)
        return type_name

    def _get_days(self, starttime, endtime):
        """Get days between (inclusive) starttime and endtime.

        Parameters
        ----------
        starttime : obspy.core.UTCDateTime
            the start time
        endtime : obspy.core.UTCDateTime
            the end time

        Returns
        -------
        array_like
            list of times, one per day, for all days between and including
            ``starttime`` and ``endtime``.

        Raises
        ------
        TimeseriesFactoryException
            if starttime is after endtime
        """
        if starttime > endtime:
            raise TimeseriesFactoryException(
                    'starttime must be before endtime')
        days = []
        day = starttime
        lastday = (endtime.year, endtime.month, endtime.day)
        while True:
            days.append(day)
            if lastday == (day.year, day.month, day.day):
                break
            # move to next day
            day = obspy.core.UTCDateTime(day.timestamp + 86400)
        return days

    def write_file(self, fh, timeseries, channels):
        """writes timeseries data to the given file object.

        Parameters
        ----------
        fh: file object
        timeseries : obspy.core.Stream
            stream containing traces to store.
        channels : array_like
            list of channels to store
        """
        IAGA2002Writer().write(fh, timeseries, channels)

    def put_timeseries(self, timeseries, starttime=None, endtime=None,
            channels=None, type=None, interval=None):
        """Store timeseries data.

        Parameters
        ----------
        timeseries : obspy.core.Stream
            stream containing traces to store.
        starttime : UTCDateTime
            time of first sample in timeseries to store.
            uses first sample if unspecified.
        endtime : UTCDateTime
            time of last sample in timeseries to store.
            uses last sample if unspecified.
        channels : array_like
            list of channels to store, optional.
            uses default if unspecified.
        type : {'definitive', 'provisional', 'quasi-definitive', 'variation'}
            data type, optional.
            uses default if unspecified.
        interval : {'daily', 'hourly', 'minute', 'monthly', 'second'}
            data interval, optional.
            uses default if unspecified.
        """
        if not self.urlTemplate.startswith('file://'):
            raise TimeseriesFactoryException('Only file urls are supported')
        channels = channels or self.channels
        type = type or self.type
        interval = interval or self.interval
        stats = timeseries[0].stats
        observatory = stats.station
        starttime = starttime or stats.starttime
        endtime = endtime or stats.endtime
        days = self._get_days(starttime, endtime)
        for day in days:
            day_filename = self._get_file_from_url(
                    self._get_url(observatory, day, type, interval))
            day_timeseries = self._get_slice(timeseries, day, interval)
            with open(day_filename, 'w') as fh:
                self.write_file(fh, day_timeseries, channels)

    def _get_file_from_url(self, url):
        """Get a file for writing.

        Ensures parent directory exists.

        Parameters
        ----------
        url : str
            Url path to IAGA2002

        Returns
        -------
        str
            path to file without file:// prefix

        Raises
        ------
        TimeseriesFactoryException
            if url does not start with file://
        """
        if not url.startswith('file://'):
            raise TimeseriesFactoryException(
                    'Only file urls are supported for writing')
        filename = url.replace('file://', '')
        parent = os.path.dirname(filename)
        if not os.path.exists(parent):
            os.makedirs(parent)
        return filename

    def _get_slice(self, timeseries, day, interval):
        """Get the first and last time for a day

        Parameters
        ----------
        timeseries : obspy.core.Stream
            timeseries to slice
        day : UTCDateTime
            time in day to slice

        Returns
        -------
        obspy.core.Stream
            sliced stream
        """
        day = day.datetime
        start = obspy.core.UTCDateTime(day.year, day.month, day.day, 0, 0, 0)
        if interval == 'minute':
            end = start + 86340.0
        else:
            end = start + 86399.999999
        return timeseries.slice(start, end)
