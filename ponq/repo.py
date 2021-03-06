import json
import os.path
from shutil import copyfile
import subprocess

def loadJSON(filename):
  with open(filename, "r") as file:
    data = json.load(file)
  return data

def parseNumber(number):
  if type(number) is int:
    return number
  else:
    return int(number, 0)

def newerThan(filea, fileb):
  return os.path.getmtime(filea) > os.path.getmtime(fileb)

firmware_directory = "/lib/firmware"


# represents a bitfiles pr regions and interactable peripherals
class Bitfile:
  def __init__(self, region, binfile, acc):
    self.region = region
    self.binfile = binfile
    self.stubRegions = []
    self.acc = acc
    self.install()

  def isFull(self):
    return self.region == "full"

  def install(self):
    firmsrc = self.acc.repo.root + "/" + self.binfile
    firmdst = firmware_directory + "/" + self.binfile
    if not os.path.exists(firmdst) or newerThan(firmsrc, firmdst):
      print("Copying file from " + firmsrc + " to " + firmdst)
      copyfile(firmsrc, firmdst)

  @staticmethod
  def fromJSON(acc, metadata):
    return Bitfile(metadata["region"], metadata["name"], acc)
    if "stubregions" in metadata:
      self.stubRegions = metadata["stubregions"]


# represents a re-programmable region
class Region:
  def __init__(self, name, blank, blocker, address, shell):
    self.name = name
    self.blocker = parseNumber(blocker)
    self.address = parseNumber(address)
    self.blankstream = Bitfile(name, blank, shell)
    self.shell = shell

  @staticmethod
  def fromJSON(metadata, shell):
    return Region(metadata["name"], metadata["blank"], metadata["bridge"], metadata["addr"], shell)

# map of slot names to numbers
sibling_slot_base = "pr0"
sibling_slot_map = {
  "pr1": 1,
  "pr2": 2
}


# represents many bitfiles containing the same hardware
class Accelerator:
  def __init__(self, name, address, repo):
    self.name = name
    self.address = parseNumber(address)
    self.repo = repo
    self.bitfiles = []
    self.registers = {}

  def install(self, repodir, destdir):
    for bitfile in self.bitfiles:
      bitfile.install(repodir, destdir)

  def generateSiblings(self):
    if self.repo.bitpatchbin is None: return # no bitpatch bin, do not generate siblings
    for basefile in self.bitfiles:                 # for all regions
      if basefile.region == sibling_slot_base and len(basefile.stubRegions) == 0:         # if region can generate siblings
        for slotname in sibling_slot_map:      # for each sibling slot
          count = len([x for x in self.bitfiles if x.region == slotname])
          if count == 0:                                  # check if sibling provided
            slotno = sibling_slot_map[slotname]
            oldpath = self.repo.root + "/" + basefile.binfile
            newfile = self.name + "_u96_slot_" + str(slotno) + ".gen.bin"
            newpath = self.repo.root + "/" + newfile
            if not os.path.exists(newpath) or newerThan(oldpath, newpath):
              print(f"Bit patching {oldpath} to {newpath} (slot {slotno})")
              self.repo.bit_patch(oldpath, newpath, slotno)
            print(f"Added generated sibling: {self.name} - {slotname}")
            self.bitfiles.append(Bitfile(slotname, newfile, self))

  @staticmethod
  def fromJSON(metadata, repo):
    address = metadata["address"] if "address" in metadata else 0
    acc = Accelerator(metadata["name"], address, repo)
    for bitfile in metadata["bitfiles"]:
      acc.bitfiles.append(Bitfile.fromJSON(acc, bitfile))
    for register in metadata["registers"]:
      acc.registers[register["name"]] = parseNumber(register["offset"])
    acc.generateSiblings()
    return acc



# represents a full bitstream which with reconfigurable regions
class Shell:
  def __init__(self, name, repo):
    self.name = name
    self.repo = repo
    self.bitfile = None
    self.regions = []

  @staticmethod
  def fromJSON(metadata, repo):
    shell = Shell(metadata["name"], repo)
    shell.bitfile = Bitfile("", metadata["bitfile"], shell)
    for region in metadata["regions"]:
      shell.regions.append(Region.fromJSON(region, shell))
    return shell



# represent a collection of bitfiles and register maps
class Repository:
  def __init__(self, root, bitpatchbin="../build/bit_patch_bin"):
    self.root = root
    self.bitpatchbin = bitpatchbin if os.path.exists(bitpatchbin) else None
    self.accs = []
    self.shells = []
    self.loadRepo()

  def bit_patch(self, infile, outfile, newslot):
    if self.bitpatchbin:
      subprocess.call([self.bitpatchbin, infile, outfile, str(newslot)])
    else: raise Exception("No bitpatchbin specified")

  def loadRepo(self):
    metadata = loadJSON(self.root + "/repo.json")
    self.loadShell(metadata["shell"])
    for accel in metadata["accelerators"]:
      self.loadAccel(accel)

  def getAccel(self, name):
    candidate = [x for x in self.accs if x.name == name]
    if len(candidate) is 0:
      self.loadAccel(name)
      candidate = [x for x in self.accs if x.name == name]
    return candidate[0]

  def getShell(self, name):
    candidate = [x for x in self.shells if x.name == name]
    if len(candidate) is 0:
      self.loadAccel(name)
      candidate = [x for x in self.shells if x.name == name]
    return candidate[0]

  def loadAccel(self, name):
    #print("REPO: Loading IP: " + name)
    filepath = self.root + "/" + name
    metadata = loadJSON(filepath + ".json")
    acc = Accelerator.fromJSON(metadata, self)
    self.accs.append(acc)

  def loadShell(self, name):
    filepath = self.root + "/" + name
    metadata = loadJSON(filepath + ".json")
    shell = Shell.fromJSON(metadata, self)
    self.shells.append(shell)
