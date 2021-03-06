""" Implements the Timer API that was once built into the bot. With some additional extensions - such as multiple running versions of the same timer.
"""

from threading import Thread
import time
import logging

global timers,timerThread

timers = {}
timerThread = None

class TimerInformation:
	function = None
	args = ()
	kwargs = {}

	countdown = -1

	singleton = False
	
	def __init__(self, function, args, kwargs, singleton):
		self.args = args
		self.kwargs = kwargs
		self.function = function
		self.singleton = singleton
		self.time = self.function._time
		self.countdown = self.time

	def __str__(self):
		return "[[ Timer %s of %s ]]" % (self.function.__name__, self.function.__module__)

	def run(self):
		if self.function(*self.args, **self.kwargs):
			self.countdown = self.time

		self.function._num_running -= 1

	def __call__(self, *a, **kw):
		self.run()

	def cancel(self):
		self.countdown = -1
		self.function._num_running -= 1

	def delay(self, time):
		self.countdown += time

	def reset(self):
		self.countdown = self.time

class TimerThread(Thread):
	def __init__(self):
		Thread.__init__(self, name="Timer Thread")
		self.logger = logger

	def run(self):

		self.run = True

		while self.run:
			global timers
			
			for mod in timers:
				toDel = []
				for timerInfo in timers[mod]:
					if timerInfo.countdown == 0:
						try:
							timerInfo.run()
						except:
							self.logger.exception("Error running timer %s", timerInfo)

						timerInfo.countdown -= 1

					elif timerInfo.countdown > 0:
						timerInfo.countdown -= 1
					else: # Countdown < 0 -- Delete
						toDel.append(timerInfo)

				for delMe in toDel:
					timers[mod].remove(delMe)

			time.sleep(1)
		self.logger.debug("Timer thread stoping.")

	def stop(self):
		self.run = False
	
def timer_start(timer, a, kw):
	global timers

	if timer._singleton and timer._num_running > 0:
		return timer._single_info # Timer is already running, and a singleton, so return the singleton's TimerInformation Instance

	logger.debug("Starting timer %s", timer.__name__)

	ti = TimerInformation(timer, a, kw, timer._singleton)

	timer._num_running += 1

	if timer._singleton:
		timer._single_info = ti

	timers[timer.__module__].append(ti)

	logger.debug(timers)

	return ti

def timer_cancel(timer):
	if not timer._singleton:
		return # Not a singleton, invalid function

	if timer._single_info is not None:
		timer._single_info.cancel()
		timer._single_info = None


def timer_delay(timer, time):
	if not timer._singleton:
		return

	if timer._single_info is not None:
		timer._single_info.delay(time)

def timer_reset(timer):
	if not timer._singleton:
		return

	if timer._single_info is not None:
		timer._single_info.reset()
	

def onLoad():

	global timerThread
	logger.debug("Starting Timer thread.")

	timerThread = TimerThread()
	timerThread.start()

	@injected
	def timer(time, singleton=False):
		def timerFunc(func):
			global timers

			mod = func.__module__
			
			if mod not in timers:
				timers[mod] = []

			func._time = time
			
			func._singleton = singleton
			func._num_running = 0

			if func._singleton:
				# Wrap some TimerInformation functions to the object, since it is a singleton
				func.cancel = lambda : timer_cancel(func)
				func.delay = lambda time : timer_delay(func, time)
				func.reset = lambda : timer_reset(func)
				# And create the var for future use
				func._single_info = None

			func.start = lambda *a, **kw : timer_start(func, a, kw)
			func.running = lambda : func._num_running

			return func
		return timerFunc

	@hook("module_unload")
	def module_unload_hook(modInfo):
		global timers

		if modInfo.name in timers:
			del timers[modInfo.name]

def onUnload():
	global timerThread

	timerThread.stop()
