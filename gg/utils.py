# GottenGeography - Utility functions used by GottenGeography
# Copyright (C) 2010 Robert Park <rbpark@exolucere.ca>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division

from os import sep as os_sep
from os.path import join, isdir, dirname, basename
from xml.parsers.expat import ParserCreate, ExpatError
from gi.repository import Gio, GLib, Clutter, Champlain
from math import acos, sin, cos, radians
from time import strftime, localtime
from math import modf as split_float
from gettext import gettext as _
from fractions import Fraction
from pyexiv2 import Rational

from territories import get_state, get_country
from build_info import PKG_DATA_DIR

def get_file(filename):
    """Find a file that's in the same directory as this program."""
    return join(PKG_DATA_DIR, filename)

def make_clutter_color(color):
    """Generate a Clutter.Color from the currently chosen color."""
    return Clutter.Color.new(
        *[x / 256 for x in [color.red, color.green, color.blue, 32768]])

################################################################################
# GSettings overrides. This allows me to interact with GSettings more easily.
################################################################################

class GSettingsSetting(Gio.Settings):
    def __init__(self, schema_name):
        Gio.Settings.__init__(self, schema_name)
        
        # These are used to avoid infinite looping.
        self._ignore_key_changed = False
        self._ignore_prop_changed = True
    
    def bind(self, key, widget, prop, flags=Gio.SettingsBindFlags.DEFAULT):
        """Don't make me specify the default flags every time."""
        Gio.Settings.bind(self, key, widget, prop, flags)
    
    def set_value(self, key, value):
        """Convert arrays to GVariants.
        
        This makes it easier to set the back button history and the window size.
        """
        use_matrix = type(value) is list
        do_override = type(value) is tuple or use_matrix
        Gio.Settings.set_value(self, key,
            GLib.Variant('aad' if use_matrix else '(ii)', value) if do_override else value)
    
    def bind_with_convert(self, key, widget, prop, key_to_prop_converter, prop_to_key_converter):
        """Recreate g_settings_bind_with_mapping from scratch.
        
        This method was shamelessly stolen from John Stowers'
        gnome-tweak-tool on May 14, 2012.
        """
        def key_changed(settings, key):
            if self._ignore_key_changed: return
            orig_value = self[key]
            converted_value = key_to_prop_converter(orig_value)
            self._ignore_prop_changed = True
            try:
                widget.set_property(prop, converted_value)
            except TypeError:
                print "TypeError: %s not a valid %s." % (converted_value, key)
            self._ignore_prop_changed = False
        
        def prop_changed(widget, param):
            if self._ignore_prop_changed: return
            orig_value = widget.get_property(prop)
            converted_value = prop_to_key_converter(orig_value)
            self._ignore_key_changed = True
            try:
                self[key] = converted_value
            except TypeError:
                print "TypeError: %s not a valid %s." % (converted_value, prop)
            self._ignore_key_changed = False
        
        self.connect("changed::" + key, key_changed)
        widget.connect("notify::" + prop, prop_changed)
        key_changed(self,key) # init default state

################################################################################
# GPS math functions. These methods convert numbers into other numbers.
################################################################################

def dms_to_decimal(degrees, minutes, seconds, sign=" "):
    """Convert degrees, minutes, seconds into decimal degrees."""
    return (-1 if sign[0] in 'SWsw' else 1) * (
        float(degrees)        +
        float(minutes) / 60   +
        float(seconds) / 3600
    )

def decimal_to_dms(decimal):
    """Convert decimal degrees into degrees, minutes, seconds."""
    remainder, degrees = split_float(abs(decimal))
    remainder, minutes = split_float(remainder * 60)
    return [
        Rational(degrees, 1),
        Rational(minutes, 1),
        float_to_rational(remainder * 60)
    ]

def float_to_rational(value):
    """Create a pyexiv2.Rational with help from fractions.Fraction."""
    frac = Fraction(abs(value)).limit_denominator(99999)
    return Rational(frac.numerator, frac.denominator)

def valid_coords(lat, lon):
    """Determine the validity of coordinates."""
    if type(lat) not in (float, int): return False
    if type(lon) not in (float, int): return False
    return abs(lat) <= 90 and abs(lon) <= 180

################################################################################
# String formatting methods. These methods manipulate strings.
################################################################################

def format_list(strings, joiner=", "):
    """Join geonames with a comma, ignoring missing names."""
    return joiner.join([name for name in strings if name])

def maps_link(lat, lon, anchor=_("View in Google Maps")):
    """Create a Pango link to Google Maps."""
    return '<a title="%s" href="http://maps.google.com/maps?q=%s,%s">Google</a>' % (anchor, lat, lon)

def format_coords(lat, lon):
    """Add cardinal directions to decimal coordinates."""
    return "%s %.5f, %s %.5f" % (
        _("N") if lat >= 0 else _("S"), abs(lat),
        _("E") if lon >= 0 else _("W"), abs(lon)
    )

################################################################################
# Map source definitions.
################################################################################

def create_map_source(id, name, license, uri, minzoom, maxzoom, tile_size, uri_format):
    renderer  = Champlain.ImageRenderer()
    map_chain = Champlain.MapSourceChain()
    factory   = Champlain.MapSourceFactory.dup_default()
    err_src   = factory.create_error_source(tile_size)
    tile_src  = Champlain.NetworkTileSource.new_full(id, name, license, uri,
        minzoom, maxzoom, tile_size, Champlain.MapProjection.MAP_PROJECTION_MERCATOR,
        uri_format, renderer)
    
    renderer   = Champlain.ImageRenderer()
    file_cache = Champlain.FileCache.new_full(100000000, None, renderer)
    
    renderer  = Champlain.ImageRenderer()
    mem_cache = Champlain.MemoryCache.new_full(100, renderer)
    
    for src in (err_src, tile_src, file_cache, mem_cache):
        map_chain.push(src)
    
    return map_chain

map_sources = {
    'osm-mapnik':
    create_map_source('osm-mapnik', 'OpenStreetMap Mapnik',
    'Map data is CC-BY-SA 2.0 OpenStreetMap contributors',
    'http://creativecommons.org/licenses/by-sa/2.0/',
    0, 18, 256, 'http://tile.openstreetmap.org/#Z#/#X#/#Y#.png'),
    
    'osm-cyclemap':
    create_map_source('osm-cyclemap', 'OpenStreetMap Cycle Map',
    'Map data is CC-BY-SA 2.0 OpenStreetMap contributors',
    'http://creativecommons.org/licenses/by-sa/2.0/',
    0, 17, 256, 'http://a.tile.opencyclemap.org/cycle/#Z#/#X#/#Y#.png'),
    
    'osm-transport':
    create_map_source('osm-transport', 'OpenStreetMap Transport Map',
    'Map data is CC-BY-SA 2.0 OpenStreetMap contributors',
    'http://creativecommons.org/licenses/by-sa/2.0/',
    0, 18, 256, 'http://tile.xn--pnvkarte-m4a.de/tilegen/#Z#/#X#/#Y#.png'),
    
    'mapquest-osm':
    create_map_source('mapquest-osm', 'MapQuest OSM',
    'Data, imagery and map information provided by MapQuest, Open Street Map and contributors',
    'http://creativecommons.org/licenses/by-sa/2.0/',
    0, 17, 256, 'http://otile1.mqcdn.com/tiles/1.0.0/osm/#Z#/#X#/#Y#.png'),
    
    'mff-relief':
    create_map_source('mff-relief', 'Maps for Free Relief',
    'Map data available under GNU Free Documentation license, Version 1.2 or later',
    'http://www.gnu.org/copyleft/fdl.html',
    0, 11, 256, 'http://maps-for-free.com/layer/relief/z#Z#/row#Y#/#Z#_#X#-#Y#.jpg')
}

################################################################################
# Class definitions.
################################################################################

class Polygon(Champlain.PathLayer):
    """Extend a Champlain.PathLayer to do things more the way I like them."""
    
    def __init__(self):
        super(Champlain.PathLayer, self).__init__()
        self.set_stroke_width(4)
    
    def append_point(self, latitude, longitude, elevation):
        """Simplify appending a point onto a polygon."""
        coord = Champlain.Coordinate.new_full(latitude, longitude)
        coord.lat = latitude
        coord.lon = longitude
        coord.ele = elevation
        self.add_node(coord)
        return coord


class Coordinates():
    """A generic object containing latitude and longitude coordinates.
    
    This class is inherited by Photograph and TrackFile and contains methods
    required by both of those classes.
    
    The geodata attribute of this class is shared across all instances of
    all subclasses of this class. When it is modified by any instance, the
    changes are immediately available to all other instances. It serves as
    a cache for data read from cities.txt, which contains geocoding data
    provided by geonames.org. All subclasses of this class can call
    self.lookup_geoname() and receive cached data if it was already
    looked up by another instance of any subclass.
    """
    
    provincestate = None
    countrycode   = None
    countryname   = None
    city          = None
    
    filename  = ""
    altitude  = None
    latitude  = None
    longitude = None
    timestamp = None
    timezone  = None
    geodata   = {}
    
    def valid_coords(self):
        """Check if this object contains valid coordinates."""
        return valid_coords(self.latitude, self.longitude)
    
    def maps_link(self):
        """Return a link to Google Maps if this object has valid coordinates."""
        if self.valid_coords():
            return maps_link(self.latitude, self.longitude)
    
    def lookup_geoname(self):
        """Search cities.txt for nearest city."""
        if not self.valid_coords():
            return
        assert self.geodata is Coordinates.geodata
        key = "%.2f,%.2f" % (self.latitude, self.longitude)
        if key in self.geodata:
            return self.set_geodata(self.geodata[key])
        near, dist = None, float('inf')
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        with open(get_file("cities.txt")) as cities:
            for city in cities:
                name, lat, lon, country, state, tz = city.split("\t")
                lat2, lon2 = radians(float(lat)), radians(float(lon))
                try:
                    delta = acos(sin(lat1) * sin(lat2) +
                                 cos(lat1) * cos(lat2) *
                                 cos(lon2  - lon1))    * 6371 # earth's radius in km
                except ValueError:
                    delta = 0
                if delta < dist:
                    dist = delta
                    near = [name, state, country, tz]
        self.geodata[key] = near
        return self.set_geodata(near)
    
    def set_geodata(self, data):
        """Apply geodata to internal attributes."""
        self.city, state, self.countrycode, tz = data
        self.provincestate = get_state(self.countrycode, state)
        self.countryname   = get_country(self.countrycode)
        self.timezone      = tz.strip()
        return self.timezone
    
    def pretty_time(self):
        """Convert epoch seconds to a human-readable date."""
        if type(self.timestamp) is int:
            return strftime("%Y-%m-%d %X", localtime(self.timestamp))
    
    def pretty_coords(self):
        """Add cardinal directions to decimal coordinates."""
        return format_coords(self.latitude, self.longitude) \
            if self.valid_coords() else _("Not geotagged")
    
    def pretty_geoname(self, multiline=True):
        """Display city, state, and country, if present."""
        names = [self.city, self.provincestate, self.countryname]
        length = sum([len(name) for name in names if name])
        return format_list(names, ',\n' if length > 35 and multiline else ', ')
    
    def pretty_elevation(self):
        """Convert elevation into a human readable format."""
        if type(self.altitude) in (float, int):
            return "%.1f%s" % (abs(self.altitude), _("m above sea level")
                        if self.altitude >= 0 else _("m below sea level"))
    
    def short_summary(self):
        """Plaintext summary of photo metadata."""
        return format_list([self.pretty_time(), self.pretty_coords(),
            self.pretty_geoname(), self.pretty_elevation()], "\n")
    
    def long_summary(self):
        """Longer summary with Pango markup."""
        return '<span %s>%s</span>\n<span %s>%s</span>' % (
            'size="larger"', basename(self.filename),
            'style="italic" size="smaller"', self.short_summary()
        )


class XMLSimpleParser:
    """A simple wrapper for the Expat XML parser."""
    
    def __init__(self, rootname, watchlist):
        self.rootname = rootname
        self.watchlist = watchlist
        self.call_start = None
        self.call_end = None
        self.element = None
        self.tracking = None
        self.state = {}
        
        self.parser = ParserCreate()
        self.parser.StartElementHandler = self.element_root
    
    def parse(self, filename, call_start, call_end):
        """Begin the loading and parsing of the XML file."""
        self.call_start = call_start
        self.call_end = call_end
        try:
            with open(filename) as xml:
                self.parser.ParseFile(xml)
        except ExpatError:
            raise IOError
   
    def element_root(self, name, attributes):
        """Called on the root XML element, we check if it's the one we want."""
        if self.rootname != None and name != self.rootname:
            raise IOError
        self.parser.StartElementHandler = self.element_start
    
    def element_start(self, name, attributes):
        """Only collect the attributes from XML elements that we care about."""
        if not self.tracking:
            if name not in self.watchlist:
                return
            if self.call_start(name, attributes):
                # Start tracking this element, accumulate everything under it.
                self.tracking = name
                self.parser.CharacterDataHandler = self.element_data
                self.parser.EndElementHandler = self.element_end
        
        if self.tracking is not None:
            self.element = name
            self.state[name] = ""
            self.state.update(attributes)
    
    def element_data(self, data):
        """Accumulate all data for an element.
        
        Expat can call this handler multiple times with data chunks.
        """
        if not data or data.strip() == '':
            return
        self.state[self.element] += data
    
    def element_end(self, name):
        """When the tag closes, pass it's data to the end callback and reset."""
        if name != self.tracking:
            return
        
        self.call_end(name, self.state)
        self.tracking = None
        self.state.clear()
        self.parser.CharacterDataHandler = None
        self.parser.EndElementHandler = None


class Struct:
    """This is a generic object which can be assigned arbitrary attributes."""
    
    def __init__(self, attributes={}):
        self.__dict__.update(attributes)

