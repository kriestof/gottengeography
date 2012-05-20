# GottenGeography - Control how the preferences are set.
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

from gi.repository import Gtk, Champlain, Clutter
from os.path import basename

from common import CommonAttributes, get_obj, map_view

class LabelController(CommonAttributes):
    """Control the behavior and creation of ChamplainLabels."""
    
    def __init__(self):
        self.select_all = get_obj("select_all_button")
        self.selection  = get_obj("photos_view").get_selection()
        self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.layer = Champlain.MarkerLayer()
        map_view.add_layer(self.layer)
        self.selection.connect("changed", self.update_highlights,
            map_view, self.selected, self.photo.viewvalues())
    
    def add(self, name):
        """Create a new ChamplainLabel and add it to the map."""
        label = Champlain.Label()
        label.set_name(name)
        label.set_text(basename(name))
        label.set_selectable(True)
        label.set_draggable(True)
        label.set_property('reactive', True)
        label.connect("enter-event", self.hover, 1.05)
        label.connect("leave-event", self.hover, 1/1.05)
        label.connect("drag-finish", self.drag_finish, self.photo)
        label.connect("button-press", self.clicked, self.selection,
            self.select_all, self.photo)
        self.layer.add_marker(label)
        return label
    
    def update_highlights(self, selection, view, selected, photos):
        """Ensure only the selected labels are highlighted."""
        selection_exists = selection.count_selected_rows() > 0
        selected.clear()
        for photo in photos:
            # Maintain the 'selected' set() for easier iterating later.
            if selection.iter_is_selected(photo.iter):
                selected.add(photo)
            photo.set_label_highlight(photo in selected, selection_exists)
    
    def clicked(self, label, event, selection, select_all, photos):
        """When a ChamplainLabel is clicked, select it in the GtkListStore.
        
        The interface defined by this method is consistent with the behavior of
        the GtkListStore itself in the sense that a normal click will select
        just one item, but Ctrl+clicking allows you to select multiple.
        """
        photo = photos[label.get_name()]
        assert photo.filename == label.get_name()
        if event.get_state() & Clutter.ModifierType.CONTROL_MASK:
            if label.get_selected(): selection.unselect_iter(photo.iter)
            else:                    selection.select_iter(photo.iter)
        else:
            select_all.set_active(False)
            selection.unselect_all()
            selection.select_iter(photo.iter)
    
    def drag_finish(self, label, event, photos):
        """Update photos with new locations after photos have been dragged."""
        photo = photos[label.get_name()]
        photo.set_location(label.get_latitude(), label.get_longitude())
        photo.manual = True
        map_view.emit("animation-completed")
    
    def hover(self, label, event, factor):
        """Scale a ChamplainLabel by the given factor."""
        label.set_scale(*[scale * factor for scale in label.get_scale()])
