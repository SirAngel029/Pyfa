import wx
from logbook import Logger

import eos.db
from eos.exception import HandledListActionError
from gui.fitCommands.helpers import DroneInfo
from service.fit import Fit
from service.market import Market


pyfalog = Logger(__name__)


class FitAddDroneCommand(wx.Command):

    def __init__(self, fitID, droneInfo):
        wx.Command.__init__(self, True, 'Add Drone')
        self.fitID = fitID
        self.droneInfo = droneInfo
        self.savedDroneInfo = None
        self.savedPosition = None

    def Do(self):
        pyfalog.debug('Doing addition of drone {} to fit {}'.format(self.droneInfo, self.fitID))
        fit = Fit.getInstance().getFit(self.fitID)
        item = Market.getInstance().getItem(self.droneInfo.itemID, eager=("attributes", "group.category"))
        # If we're not adding any active drones, check if there's an inactive stack
        # with enough space for new drones and use it
        if self.droneInfo.amountActive == 0:
            for drone in fit.drones.find(item):
                if (
                    drone is not None and drone.amountActive == 0 and
                    drone.amount + self.droneInfo.amount) <= max(5, fit.extraAttributes["maxActiveDrones"]
                ):
                    self.savedDroneInfo = DroneInfo.fromDrone(drone)
                    self.savedPosition = fit.drones.index(drone)
                    drone.amount += self.droneInfo.amount
                    eos.db.commit()
                    return True
        # Do new stack otherwise
        drone = self.droneInfo.toDrone()
        if drone is None:
            return False
        if not drone.fits(fit):
            pyfalog.warning('Drone does not fit')
            return False
        try:
            fit.drones.append(drone)
        except HandledListActionError:
            pyfalog.warning('Failed to append to list')
            eos.db.commit()
            return False
        eos.db.commit()
        self.savedPosition = fit.drones.index(drone)
        return True

    def Undo(self):
        pyfalog.debug('Undoing addition of drone {} to fit {}'.format(self.droneInfo, self.fitID))
        if self.savedDroneInfo is not None:
            fit = Fit.getInstance().getFit(self.fitID)
            drone = fit.drones[self.savedPosition]
            drone.amount = self.savedDroneInfo.amount
            drone.amountActive = self.savedDroneInfo.amountActive
            return True
        from .localRemove import FitRemoveDroneCommand
        cmd = FitRemoveDroneCommand(fitID=self.fitID, position=self.savedPosition, amount=self.droneInfo.amount)
        return cmd.Do()