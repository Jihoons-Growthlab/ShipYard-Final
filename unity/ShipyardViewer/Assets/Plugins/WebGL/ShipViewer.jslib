mergeInto(LibraryManager.library, {
  ShipViewer_NotifyReady: function () {
    if (Module.canvas) Module.canvas.dispatchEvent(new CustomEvent('shipviewer-ready'));
  },
  ShipViewer_NotifyHover: function (active) {
    if (Module.canvas) Module.canvas.dispatchEvent(new CustomEvent('shipviewer-hover', { detail: !!active }));
  },
  ShipViewer_FleetEvent: function (slot, selected) {
    if (Module.canvas) Module.canvas.dispatchEvent(new CustomEvent(selected ? 'shipyard-select' : 'shipyard-hover', { detail: slot }));
  }
});
