# Copyright 2017 British Broadcasting Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import calendar
import time
import re

__all__ = ["TsValueError", "TimeOffset", "Timestamp"]


MAX_NANOSEC = 1000000000
MAX_SECONDS = 281474976710656

# The UTC leap seconds table below was extracted from the information provided at
# http://www.ietf.org/timezones/data/leap-seconds.list
#
# The order has been reversed.
# The NTP epoch seconds have been converted to Unix epoch seconds. The difference between
# the NTP epoch at 1 Jan 1900 and the Unix epoch at 1 Jan 1970 is 2208988800 seconds

UTC_LEAP = [
# || UTC SEC  |  TAI SEC - 1 ||
  (1483228800, 1483228836),    # 1 Jan 2017, 37 leap seconds
  (1435708800, 1435708835),    # 1 Jul 2015, 36 leap seconds
  (1341100800, 1341100834),    # 1 Jul 2012, 35 leap seconds
  (1230768000, 1230768033),    # 1 Jan 2009, 34 leap seconds
  (1136073600, 1136073632),    # 1 Jan 2006, 33 leap seconds
  ( 915148800,  915148831),    # 1 Jan 1999, 32 leap seconds
  ( 867715200,  867715230),    # 1 Jul 1997, 31 leap seconds
  ( 820454400,  820454429),    # 1 Jan 1996, 30 leap seconds
  ( 773020800,  773020828),    # 1 Jul 1994, 29 leap seconds
  ( 741484800,  741484827),    # 1 Jul 1993, 28 leap seconds
  ( 709948800,  709948826),    # 1 Jul 1992, 27 leap seconds
  ( 662688000,  662688025),    # 1 Jan 1991, 26 leap seconds
  ( 631152000,  631152024),    # 1 Jan 1990, 25 leap seconds
  ( 567993600,  567993623),    # 1 Jan 1988, 24 leap seconds
  ( 489024000,  489024022),    # 1 Jul 1985, 23 leap seconds
  ( 425865600,  425865621),    # 1 Jul 1983, 22 leap seconds
  ( 394329600,  394329620),    # 1 Jul 1982, 21 leap seconds
  ( 362793600,  362793619),    # 1 Jul 1981, 20 leap seconds
  ( 315532800,  315532818),    # 1 Jan 1980, 19 leap seconds
  ( 283996800,  283996817),    # 1 Jan 1979, 18 leap seconds
  ( 252460800,  252460816),    # 1 Jan 1978, 17 leap seconds
  ( 220924800,  220924815),    # 1 Jan 1977, 16 leap seconds
  ( 189302400,  189302414),    # 1 Jan 1976, 15 leap seconds
  ( 157766400,  157766413),    # 1 Jan 1975, 14 leap seconds
  ( 126230400,  126230412),    # 1 Jan 1974, 13 leap seconds
  (  94694400,   94694411),    # 1 Jan 1973, 12 leap seconds
  (  78796800,   78796810),    # 1 Jul 1972, 11 leap seconds
  (  63072000,   63072009),    # 1 Jan 1972, 10 leap seconds
]


class TsValueError(Exception):
    """ Raised when the time offset or timestamp input valid is invalid """
    def __init__(self, msg):
        super(TsValueError, self).__init__(msg)
        self.msg = msg


def _parse_seconds_fraction(frac):
    """ Parse the fraction part of a timestamp seconds, using maximum 9 digits
    Returns the nanoseconds
    """
    ns = 0
    mult = MAX_NANOSEC
    for c in frac:
        if c < '0' or c > '9' or int(mult) < 1:
            break
        mult = mult / 10
        ns += mult * int(c)
    return ns

def _parse_iso8601(iso8601):
    """ Limited ISO 8601 timestamp parse; expands YYYY-MM-DDThh:mm:ss.s
    Returns tuple of (year, month, day, hours, mins, seconds, nanoseconds)
    """
    iso_date_time = iso8601.split("T")
    if len(iso_date_time) != 2:
        raise TsValueError("invalid or unsupported ISO 8601 UTC format")
    iso_date = iso_date_time[0].split("-")
    iso_time = iso_date_time[1].split(":")
    if len(iso_date) != 3 or len(iso_time) != 3:
        raise TsValueError("invalid or unsupported ISO 8601 UTC format")
    sec_frac = iso_time[2].split(".")
    if len(sec_frac) != 1 and len(sec_frac) != 2:
        raise TsValueError("invalid or unsupported ISO 8601 UTC format")
    sec = sec_frac[0]
    ns = 0
    if len(sec_frac) > 1:
        ns = _parse_seconds_fraction(sec_frac[1])
    return (int(iso_date[0]), int(iso_date[1]), int(iso_date[2]), int(iso_time[0]), int(iso_time[1]), int(sec), ns)


class TimeOffset(object):
    ROUND_DOWN = 0
    ROUND_NEAREST = 1
    ROUND_UP = 2

    def __init__(self, sec=0, ns=0, sign=1):
        self.sec = int(sec)
        self.ns = int(ns)
        self.sign = int(sign)
        self._make_valid()

    @classmethod
    def from_timeoffset(cls, toff):
        return cls(sec=toff.sec, ns=toff.ns, sign=toff.sign)

    @classmethod
    def get_interval_fraction(cls, rate_num, rate_den=1, factor=1):
        if rate_num <= 0 or rate_den <= 0:
            raise TsValueError("invalid rate")
        if factor < 1:
            raise TsValueError("invalid interval factor")
        sec = rate_den // (rate_num * factor)
        rem = rate_den % (rate_num * factor)
        ns = MAX_NANOSEC * rem // (rate_num * factor)
        return cls(sec=sec, ns=ns)

    @classmethod
    def from_sec_frac(cls, toff_str):
        sec_frac = toff_str.split(".")
        if len(sec_frac) != 1 and len(sec_frac) != 2:
            raise TsValueError("invalid second.fraction format")
        sec = int(sec_frac[0])
        sign = 1
        if sec < 0:
            sign = -1
            sec = abs(sec)
        ns = 0
        if len(sec_frac) > 1:
            ns = _parse_seconds_fraction(sec_frac[1])
        return cls(sec=sec, ns=ns, sign=sign)

    @classmethod
    def from_sec_nsec(cls, toff_str):
        sec_frac = toff_str.split(":")
        if len(sec_frac) != 1 and len(sec_frac) != 2:
            raise TsValueError("invalid second:nanosecond format")
        sec = int(sec_frac[0])
        sign = 1
        if sec < 0:
            sign = -1
            sec = abs(sec)
        ns = 0
        if len(sec_frac) > 1:
            ns = int(sec_frac[1])
        return cls(sec=sec, ns=ns, sign=sign)

    @classmethod
    def from_str(cls, toff_str):
        if '.' in toff_str:
            return cls.from_sec_frac(toff_str)
        else:
            return cls.from_sec_nsec(toff_str)

    @classmethod
    def from_count(cls, count, rate_num, rate_den=1):
        if rate_num <= 0 or rate_den <= 0:
            raise TsValueError("invalid rate")
        abs_count = abs(count)
        sec = (abs_count * rate_den) // rate_num
        rem = (abs_count * rate_den) % rate_num
        ns = (rem * MAX_NANOSEC) // rate_num
        sign = 1
        if count < 0:
            sign = -1
        return cls(sec=sec, ns=ns, sign=sign)

    @classmethod
    def from_millisec(cls, millisec):
        abs_millisec = abs(millisec)
        sec = abs_millisec // 1000
        ns = (abs_millisec % 1000) * 1000000
        sign = 1
        if millisec < 0:
            sign = -1
        return cls(sec=sec, ns=ns, sign=sign)

    @classmethod
    def from_microsec(cls, microsec):
        abs_microsec = abs(microsec)
        sec = abs_microsec // 1000000
        ns = (abs_microsec % 1000000) * 1000
        sign = 1
        if microsec < 0:
            sign = -1
        return cls(sec=sec, ns=ns, sign=sign)

    @classmethod
    def from_nanosec(cls, nanosec):
        abs_nanosec = abs(nanosec)
        sec = abs_nanosec // MAX_NANOSEC
        ns = abs_nanosec % MAX_NANOSEC
        sign = 1
        if nanosec < 0:
            sign = -1
        return cls(sec=sec, ns=ns, sign=sign)


    def is_null(self):
        return self.sec == 0 and self.ns == 0

    def set_value(self, sec=0, ns=0, sign=1):
        self.sec = sec
        self.ns = ns
        self.sign = sign
        self._make_valid()

    def to_sec_nsec(self):
        """ Convert to <seconds>:<nanoseconds>
        """
        return u"{}:{}".format(self.sign * self.sec, self.ns)

    def to_sec_frac(self, fixed_size=False):
        """ Convert to <seconds>.<fraction>
        """
        return u"{}.{}".format(self.sign * self.sec, self._get_fractional_seconds(fixed_size=fixed_size))

    def to_count(self, rate_num, rate_den=1, rounding=ROUND_NEAREST):
        if rate_num <= 0 or rate_den <= 0:
            raise TsValueError("invalid rate")
        abs_off = self.__abs__()
        use_rounding = rounding
        if self.sign < 0:
            if use_rounding == self.ROUND_UP:
                use_rounding = self.ROUND_DOWN
            elif use_rounding == self.ROUND_DOWN:
                use_rounding = self.ROUND_UP
        if use_rounding == self.ROUND_DOWN:
            rnd_off = TimeOffset(0, 1)
        elif use_rounding == self.ROUND_NEAREST:
            rnd_off = TimeOffset.get_interval_fraction(rate_num, rate_den, 2)
        else:
            rnd_off = TimeOffset.get_interval_fraction(rate_num, rate_den, 1) - TimeOffset(0, 1)
        if rnd_off.sign > 0:
            abs_off += rnd_off

        # off_at_rate = (off_sec + off_nsec) / (rate_den / rate_num)
        #             = (off_sec x rate_num / rate_den) + (off_nsec x rate_num) / rate_den)
        #             = {f1} + {f2}
        # reduce {f1} as follows: a*b/c = ((a/c)*c + a%c) * b) / c = (a/c)*b + (a%c)*b/c
        f1_whole = (abs_off.sec // rate_den) * rate_num
        f1_nsec = (abs_off.sec % rate_den) * rate_num * MAX_NANOSEC // rate_den
        f2_nsec = abs_off.ns * rate_num // rate_den
        return self.sign * (f1_whole + (f1_nsec + f2_nsec) // MAX_NANOSEC)

    def to_millisec(self, rounding=ROUND_NEAREST):
        use_rounding = rounding
        if self.sign < 0:
            if use_rounding == self.ROUND_UP:
                use_rounding = self.ROUND_DOWN
            elif use_rounding == self.ROUND_DOWN:
                use_rounding = self.ROUND_UP
        round_ns = 0
        if use_rounding == self.ROUND_NEAREST:
            round_ns = 1000000 // 2
        elif use_rounding == self.ROUND_UP:
            round_ns = 1000000 - 1
        return self.sign * (self.sec*1000 + (self.ns + round_ns)//1000000)

    def to_microsec(self, rounding=ROUND_NEAREST):
        use_rounding = rounding
        if self.sign < 0:
            if use_rounding == self.ROUND_UP:
                use_rounding = self.ROUND_DOWN
            elif use_rounding == self.ROUND_DOWN:
                use_rounding = self.ROUND_UP
        round_ns = 0
        if use_rounding == self.ROUND_NEAREST:
            round_ns = 1000 // 2
        elif use_rounding == self.ROUND_UP:
            round_ns = 1000 - 1
        return self.sign * (self.sec*1000000 + (self.ns + round_ns)//1000)

    def to_nanosec(self):
        return self.sign * (self.sec*MAX_NANOSEC + self.ns)

    def normalise(self, rate_num, rate_den=1, rounding=ROUND_NEAREST):
        return self.from_count(self.to_count(rate_num, rate_den, rounding), rate_num, rate_den)

    def compare(self, other):
        if self.sign != other.sign:
            return self.sign
        elif self.sec < other.sec:
            return -self.sign
        elif self.sec > other.sec:
            return self.sign
        elif self.ns < other.ns:
            return -self.sign
        elif self.ns > other.ns:
            return self.sign
        else:
            return 0

    def __repr__(self):
        return self.to_sec_nsec()

    def __abs__(self):
        return TimeOffset(self.sec, self.ns, 1)

    def __eq__(self, other):
        return self.compare(other) == 0

    def __ne__(self, other):
        return self.compare(other) != 0

    def __lt__(self, other):
        return self.compare(other) < 0

    def __le__(self, other):
        return self.compare(other) <= 0

    def __gt__(self, other):
        return self.compare(other) > 0

    def __ge__(self, other):
        return self.compare(other) >= 0

    def __add__(self, other):
        toff = TimeOffset(self.sec, self.ns, self.sign)
        toff += other
        return toff

    def __sub__(self, other):
        toff = TimeOffset(self.sec, self.ns, self.sign)
        toff -= other
        return toff

    def __iadd__(self, other):
        sec = self.sign*self.sec + other.sign*other.sec
        ns = self.sign*self.ns + other.sign*other.ns
        self._complete_iadd_or_isub(sec, ns)
        return self

    def __isub__(self, other):
        sec = self.sign*self.sec - other.sign*other.sec
        ns = self.sign*self.ns - other.sign*other.ns
        self._complete_iadd_or_isub(sec, ns)
        return self

    def __mul__(self, anint):
        toff = TimeOffset(self.sec, self.ns, self.sign)
        toff *= anint
        return toff

    def __rmul__(self, anint):
        toff = TimeOffset(self.sec, self.ns, self.sign)
        toff *= anint
        return toff

    def __div__(self, anint):
        toff = TimeOffset(self.sec, self.ns, self.sign)
        toff /= anint
        return toff

    def __imul__(self, anint):
        abs_anint = abs(anint)
        ns_sec = self.ns * (abs_anint // MAX_NANOSEC)
        ns = self.ns * (abs_anint % MAX_NANOSEC)

        self.sec = self.sec * abs_anint + ns_sec + ns // MAX_NANOSEC
        self.ns = ns % MAX_NANOSEC
        if anint < 0:
            self.sign *= -1
        self._make_valid()
        return self

    def __idiv__(self, anint):
        abs_anint = abs(anint)
        sec = self.sec // abs_anint
        ns = int((self.ns + (self.sec % abs_anint) * MAX_NANOSEC) / abs_anint + 5e-10)

        self.sec = sec + ns // MAX_NANOSEC
        self.ns = ns % MAX_NANOSEC
        if anint < 0:
            self.sign *= -1
        self._make_valid()
        return self

    def _complete_iadd_or_isub(self, sec, ns):
        if ns >= MAX_NANOSEC:
            ns -= MAX_NANOSEC
            sec += 1
        elif -ns >= MAX_NANOSEC:
            ns += MAX_NANOSEC
            sec -= 1
        if sec < 0 and ns > 0:
            ns -= MAX_NANOSEC
            sec += 1
        elif sec > 0 and ns < 0:
            ns += MAX_NANOSEC
            sec -= 1

        if sec < 0 or ns < 0:
            self.sign = -1
            self.sec = abs(sec)
            self.ns = abs(ns)
        else:
            self.sign = 1
            self.sec = sec
            self.ns = ns
        self._make_valid()

    def _get_fractional_seconds(self, fixed_size=False):
        div = MAX_NANOSEC / 10
        rem = self.ns
        sec_frac = ""

        for i in range(0, 9):
            if not fixed_size and i > 0 and rem == 0:
                break

            sec_frac += '%i' % (rem / div)
            rem %= div
            div /= 10

        return sec_frac

    def _make_valid(self):
        if self.sign >= 0 or (self.sec == 0 and self.ns == 0):
            self.sign = 1
        else:
            self.sign = -1
        if self.sec < 0:
            self.sec = 0
            self.ns = 0
            self.sign = 1
        elif self.ns < 0:
            self.ns = 0
        elif self.ns >= MAX_NANOSEC:
            self.ns = MAX_NANOSEC - 1


class Timestamp(TimeOffset):
    def __init__(self, sec=0, ns=0, sign=1):
        super(Timestamp, self).__init__(sec, ns, sign)

    @classmethod
    def from_tai_sec_frac(cls, ts_str):
        return cls.from_sec_frac(ts_str)

    @classmethod
    def from_tai_sec_nsec(cls, ts_str):
        return cls.from_sec_nsec(ts_str)

    @classmethod
    def from_iso8601_utc(cls, iso8601utc):
        if not iso8601utc.endswith('Z'):
            raise TsValueError("missing 'Z' at end of ISO 8601 UTC format")
        year, month, day, hour, minute, second, ns = _parse_iso8601(iso8601utc[:-1])
        gmtuple = (year, month, day, hour, minute, second - (second == 60))
        secs_since_epoch = calendar.timegm(gmtuple)
        return cls.from_utc(secs_since_epoch, ns, (second == 60))

    @classmethod
    def from_smpte_timelabel(cls, timelabel):
        r = re.compile(r'(\d+)-(\d+)-(\d+)T(\d+):(\d+):(\d+)F(\d+) (\d+)/(\d+) UTC([-\+])(\d+):(\d+) TAI([-\+])(\d+)')
        m = r.match(timelabel)
        if m is None:
            raise TsValueError("invalid SMPTE Time Label string format")
        groups = m.groups()
        leap_sec = int(int(groups[5]) == 60)
        local_tm_sec = calendar.timegm(time.struct_time((int(groups[0]), int(groups[1]), int(groups[2]),
                                                         int(groups[3]), int(groups[4]), int(groups[5]) - leap_sec,
                                                         0, 0, 0)))
        rate_num = int(groups[7])
        rate_den = int(groups[8])
        utc_sign = 1
        if groups[9] == '-':
            utc_sign = -1
        tai_sign = 1
        if groups[12] == '-':
            tai_sign = -1
        tai_seconds = local_tm_sec + leap_sec - utc_sign*(int(groups[10])*60*60 + int(groups[11])*60) - tai_sign*int(groups[13])
        count = Timestamp(tai_seconds, 0).to_count(rate_num, rate_den, cls.ROUND_UP)
        count += int(groups[6])
        return cls.from_count(count, rate_num, rate_den)

    @classmethod
    def from_str(cls, ts_str):
        if 'F' in ts_str:
            return cls.from_smpte_timelabel(ts_str)
        elif 'T' in ts_str:
            return cls.from_iso8601_utc(ts_str)
        else:
            return super(Timestamp, cls).from_str(ts_str)

    @classmethod
    def from_utc(cls, utc_sec, utc_ns, is_leap=False):
        leap_sec = 0
        for tbl_sec, tbl_tai_sec_minus_1 in UTC_LEAP:
            if utc_sec >= tbl_sec:
                leap_sec = (tbl_tai_sec_minus_1 + 1) - tbl_sec
                break
        return cls(sec=utc_sec+leap_sec+is_leap, ns=utc_ns)

    def get_leap_seconds(self):
        """ Get the UTC leaps seconds.
        Returns the number of leap seconds that the timestamp is adjusted by when
        converting to UTC.
        """
        leap_sec = 0
        for utc_sec, tai_sec_minus_1 in UTC_LEAP:
            if self.sec >= tai_sec_minus_1:
                leap_sec = (tai_sec_minus_1 + 1) - utc_sec
                break

        return leap_sec

    def to_tai_sec_nsec(self):
        return self.to_sec_nsec()

    def to_tai_sec_frac(self, fixed_size=False):
        return self.to_sec_frac(fixed_size=fixed_size)

    def to_utc(self):
        """ Convert to UTC.
        Returns a tuple of (seconds, nanoseconds, is_leap), where `is_leap` is
        `True` when the input time corresponds exactly to a UTC leap second.
        Note that this deliberately returns a tuple, to try and avoid confusion.
        """
        leap_sec = 0
        is_leap = False
        for utc_sec, tai_sec_minus_1 in UTC_LEAP:
            if self.sec >= tai_sec_minus_1:
                leap_sec = (tai_sec_minus_1 + 1) - utc_sec
                is_leap = self.sec == tai_sec_minus_1
                break

        return (self.sec - leap_sec, self.ns, is_leap)

    def to_iso8601_utc(self):
        """ Get printed representation in ISO8601 format (UTC)
        YYYY-MM-DDThh:mm:ss.s
        where `s` is fractional seconds at nanosecond precision (always 9-chars wide)
        """
        utc_s, utc_ns, is_leap = self.to_utc()
        utc_bd = time.gmtime(utc_s)
        frac_sec = self._get_fractional_seconds(fixed_size=True)
        leap_sec = int(is_leap)
        return '%04d-%02d-%02dT%02d:%02d:%02d.%sZ' % (utc_bd.tm_year, utc_bd.tm_mon, utc_bd.tm_mday, utc_bd.tm_hour, utc_bd.tm_min, utc_bd.tm_sec + leap_sec, frac_sec)

    def to_smpte_timelabel(self, rate_num, rate_den=1, utc_offset=None):
        if rate_num <= 0 or rate_den <= 0:
            raise TsValueError("invalid rate")
        count = self.to_count(rate_num, rate_den)
        normalised_ts = Timestamp.from_count(count, rate_num, rate_den)
        tai_seconds = normalised_ts.sec
        count_on_or_after_second = Timestamp(tai_seconds, 0).to_count(rate_num, rate_den, self.ROUND_UP)
        count_within_second = count - count_on_or_after_second

        utc_sec, utc_ns, is_leap = normalised_ts.to_utc()
        leap_sec = int(is_leap)

        if utc_offset is None:
            # calculate local time offset
            utc_offset_sec = time.timezone
            lt = time.localtime(utc_sec)
            if lt.tm_isdst > 0:
                utc_offset_sec += 60*60
        else:
            utc_offset_sec = utc_offset
        utc_offset_sec_abs = abs(utc_offset_sec)
        utc_offset_hour = utc_offset_sec_abs // (60*60)
        utc_offset_min = (utc_offset_sec_abs % (60*60)) // 60
        utc_sign_char = '+'
        if utc_offset_sec < 0:
            utc_sign_char = '-'

        utc_bd = time.gmtime(utc_sec + utc_offset_sec)

        tai_offset = utc_sec + leap_sec - tai_seconds
        tai_sign_char = '+'
        if tai_offset < 0:
            tai_sign_char = '-'

        return '%04d-%02d-%02dT%02d:%02d:%02dF%02u %u/%u UTC%c%02u:%02u TAI%c%u' % (
                    utc_bd.tm_year, utc_bd.tm_mon, utc_bd.tm_mday,
                    utc_bd.tm_hour, utc_bd.tm_min, utc_bd.tm_sec + leap_sec,
                    count_within_second,
                    rate_num, rate_den,
                    utc_sign_char, utc_offset_hour, utc_offset_min,
                    tai_sign_char, abs(tai_offset))


    def _make_valid(self):
        super(Timestamp, self)._make_valid()
        if self.sign < 0:
            self.sec = 0
            self.ns = 0
            self.sign = 1
        elif self.sec >= MAX_SECONDS:
            self.sec = MAX_SECONDS - 1
            self.ns = MAX_NANOSEC - 1


if __name__ == '__main__':
    import sys

    arg = sys.argv[1]

    ts = Timestamp.from_str(arg)

    if ts is not None:
        print "ips-tai-nsec     {}".format(ts.to_tai_sec_nsec())
        print "ips-tai-frac     {}".format(ts.to_tai_sec_frac())
        print "utc              {}".format(ts.to_iso8601_utc())
        print "utc-secs         {}".format(ts.to_utc()[0])
        print "smpte time label {}".format(ts.to_smpte_timelabel(50, 1))
        sys.exit(0)

    else:
        sys.exit(1)
