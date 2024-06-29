"""
rayIntersector.py

This script defines a Maya node that projects a ray from a transform and finds its
intersection with scene geometry. The node returns the world space coordinate of
the first piece of geometry it intersects, or the input transform position if no
intersection is found.

Author: computerologist
Date: June 29, 2024
Version: 0.1
"""

import maya.api.OpenMaya as om
import maya.cmds as mc

def maya_useNewAPI():
    pass

class RayIntersector(om.MPxNode):
    kNodeName = "rayIntersector"
    kNodeId = om.MTypeId(0x00100010)

    def __init__(self):
        super(RayIntersector, self).__init__()

    @classmethod
    def creator(cls):
        return cls()

    @classmethod
    def initialize(cls):
        mAttr = om.MFnMatrixAttribute()
        nAttr = om.MFnNumericAttribute()
        eAttr = om.MFnEnumAttribute()

        cls.inputMatrixAttr = mAttr.create("inputMatrix", "cm", om.MFnMatrixAttribute.kDouble)
        mAttr.storable = False
        mAttr.readable = True
        mAttr.writable = True

        cls.outputTranslateAttr = nAttr.createPoint("outputTranslate", "int")
        nAttr.storable = False
        nAttr.readable = True
        nAttr.writable = False

        cls.rayAxisAttr = eAttr.create("rayAxis", "ra", 5)  # Default to -Z
        for i, axis in enumerate(["X", "Y", "Z", "-X", "-Y", "-Z"]):
            eAttr.addField(axis, i)

        eAttr.storable = True
        eAttr.readable = True
        eAttr.writable = True

        cls.addAttribute(cls.inputMatrixAttr)
        cls.addAttribute(cls.outputTranslateAttr)
        cls.addAttribute(cls.rayAxisAttr)

        cls.attributeAffects(cls.inputMatrixAttr, cls.outputTranslateAttr)
        cls.attributeAffects(cls.rayAxisAttr, cls.outputTranslateAttr)

    def compute(self, plug, dataBlock):
        if plug == self.outputTranslateAttr:
            try:
                inputHandle = dataBlock.inputValue(self.inputMatrixAttr)
                inputMatrix = inputHandle.asMatrix()
                
                rayAxisHandle = dataBlock.inputValue(self.rayAxisAttr)
                rayAxis = rayAxisHandle.asShort()
                
                transformPosition = om.MPoint(inputMatrix.getElement(3, 0),
                                           inputMatrix.getElement(3, 1),
                                           inputMatrix.getElement(3, 2))
                
                # Extract transform direction based on selected axis
                if rayAxis == 0:  # X
                    transformDirection = om.MVector(inputMatrix.getElement(0, 0),
                                                 inputMatrix.getElement(0, 1),
                                                 inputMatrix.getElement(0, 2)).normal()
                elif rayAxis == 1:  # Y
                    transformDirection = om.MVector(inputMatrix.getElement(1, 0),
                                                 inputMatrix.getElement(1, 1),
                                                 inputMatrix.getElement(1, 2)).normal()
                elif rayAxis == 2:  # Z
                    transformDirection = om.MVector(inputMatrix.getElement(2, 0),
                                                 inputMatrix.getElement(2, 1),
                                                 inputMatrix.getElement(2, 2)).normal()
                elif rayAxis == 3:  # -X
                    transformDirection = om.MVector(-inputMatrix.getElement(0, 0),
                                                 -inputMatrix.getElement(0, 1),
                                                 -inputMatrix.getElement(0, 2)).normal()
                elif rayAxis == 4:  # -Y
                    transformDirection = om.MVector(-inputMatrix.getElement(1, 0),
                                                 -inputMatrix.getElement(1, 1),
                                                 -inputMatrix.getElement(1, 2)).normal()
                else:  # -Z (default)
                    transformDirection = om.MVector(-inputMatrix.getElement(2, 0),
                                                 -inputMatrix.getElement(2, 1),
                                                 -inputMatrix.getElement(2, 2)).normal()

                intersectionPoint = self.traceRay(transformPosition, transformDirection)

                outputHandle = dataBlock.outputValue(self.outputTranslateAttr)
                if intersectionPoint:
                    outputHandle.setMFloatVector(om.MFloatVector(intersectionPoint))
                else:
                    outputHandle.setMFloatVector(om.MFloatVector(transformPosition))

                dataBlock.setClean(plug)
                
            except Exception as e:
                print(f"Error in compute: {str(e)}")
                return

    def traceRay(self, origin, direction):
        """
        Traces a ray from the given origin in the given direction and returns
        the closest intersection point with visible scene geometry.

        Args:
            origin (om.MPoint): The starting point of the ray
            direction (om.MVector): The direction of the ray

        Returns:
            om.MPoint or None: The closest intersection point, or None if no intersection is found
        """
        # Create a ray
        raySource = om.MFloatPoint(origin)
        rayDirection = om.MFloatVector(direction)

        # Prepare for intersection test
        dagIterator = om.MItDag(om.MItDag.kDepthFirst, om.MFn.kMesh)
        intersectionPoint = None
        closestDistance = float('inf')

        while not dagIterator.isDone():
            dagPath = dagIterator.getPath()

            # Check if the mesh or its transform is visible
            if self.isVisible(dagPath):
                fnMesh = om.MFnMesh(dagPath)
                #  intersection test
                try:
                    hitPoint, hitRayParam, hitFace, hitTriangle, hitBary1, hitBary2 = fnMesh.closestIntersection(
                        raySource, rayDirection, om.MSpace.kWorld, float('inf'), False
                    )

                    if hitPoint is not None:
                        distance = (hitPoint - raySource).length()
                        if distance < closestDistance:
                            closestDistance = distance
                            intersectionPoint = om.MPoint(hitPoint)
                except:
                    # If closestIntersection fails, just continue to the next mesh
                    pass

            dagIterator.next()

        return intersectionPoint  # This will be None if no intersection was found

    def isVisible(self, dagPath):
        """
        Check if the given DAG path (mesh or its transform) is visible.

        Args:
            dagPath (om.MDagPath): The DAG path to check

        Returns:
            bool: True if the object is visible, False otherwise
        """
        # Check visibility of the shape node and all parent transforms
        while dagPath.length() > 0:
            currentNode = om.MFnDependencyNode(dagPath.node())

            if currentNode.hasAttribute("visibility"):
                visPlug = currentNode.findPlug("visibility", False)
                if not visPlug.asBool():
                    return False

            # Check intermediate object attribute (for shapes)
            if currentNode.hasAttribute("intermediateObject"):
                intPlug = currentNode.findPlug("intermediateObject", False)
                if intPlug.asBool():
                    return False

            # Move up
            if dagPath.length() <= 1:
                break
            dagPath.pop(1)
        return True

class RaySceneIntersectorCommand(om.MPxCommand):
    kCommandName = "raySceneIntersector"

    def __init__(self):
        super(RaySceneIntersectorCommand, self).__init__()
        self.original_selection = []

    @staticmethod
    def creator():
        return RaySceneIntersectorCommand()

    def doIt(self, args):
        try:
            #om.MGlobal.displayInfo("Starting raySceneIntersector command")

            # Store the original selection
            self.original_selection = mc.ls(sl=True, l=True)

            argData = om.MArgDatabase(self.syntax(), args)

            transforms = []
            if argData.isFlagSet('-t'):
                try:
                    numUses = argData.numberOfFlagUses('-t')
                    for j in range(numUses):
                        arg_list = argData.getFlagArgumentList('-t', j)
                        transform = arg_list.asString(0)
                        transforms.append(transform)
                except Exception as e:
                    om.MGlobal.displayWarning(f"Error retrieving arguments for -t flag: {str(e)}")
                #om.MGlobal.displayInfo(f"transforms: {transforms}")

            else:
                # If no transforms are provided, use the current selection
                sel = mc.ls(sl=1, l=1)
                for item in sel:
                    if mc.nodeType(item) in ['joint', 'transform']:
                        transforms.append(item)
                    else:
                        parents = mc.listRelatives(item, p=1)
                        if parents:
                            if mc.nodeType(parents[0]) in ['joint', 'transform']:
                                transforms.append(parents[0])

            #om.MGlobal.displayInfo(f"Final transforms list: {transforms}")

            name = "rayIntersector1"
            if argData.isFlagSet('-n'):
                name = argData.flagArgumentString('-n', 0)

            #om.MGlobal.displayInfo(f"Name: {name}")

            axis = 5
            if argData.isFlagSet('-a'):
                axis = argData.flagArgumentInt('-a', 0)

            #om.MGlobal.displayInfo(f"Axis: {axis}")

            # Perform the ray intersection for each transform
            created_nodes = []
            for i, transform in enumerate(transforms):
                node_name = f"{name}_{i + 1}" if i > 0 else name
                ri = mc.createNode('rayIntersector', name=node_name)
                loc = mc.spaceLocator(name=f"locator_{node_name}")[0]
                mc.connectAttr(f"{transform}.worldMatrix[0]", f"{ri}.inputMatrix")
                mc.connectAttr(f"{ri}.outputTranslate", f"{loc}.t")
                mc.setAttr(f"{ri}.rayAxis", axis)
                created_nodes.extend([ri, loc])

            #om.MGlobal.displayInfo("Command execution completed")
            self.setResult(created_nodes)

        except Exception as e:
            om.MGlobal.displayError(f"Error in raySceneIntersector command: {str(e)}")
            om.MGlobal.displayError(f"Error type: {type(e)}")
            om.MGlobal.displayError(f"Error args: {e.args}")
            raise

        finally:
            # Restore the original selection
            if self.original_selection:
                try:
                    mc.select(self.original_selection, replace=True)
                except ValueError as ve:
                    om.MGlobal.displayError(f"cannot restore selection")
            else:
                mc.select(clear=True)

    @staticmethod
    def syntaxCreator():
        syntax = om.MSyntax()
        try:
            syntax.addFlag('-t', '-transforms', om.MSyntax.kString)
            syntax.makeFlagMultiUse('-t')
            syntax.addFlag('-n', '-name', om.MSyntax.kString)
            syntax.addFlag('-a', '-axis', om.MSyntax.kLong)
        except Exception as e:
            om.MGlobal.displayError(f"Error in syntaxCreator: {str(e)}")
        return syntax

def initializePlugin(plugin):
    vendor = "computerologist"
    version = "0.1"

    pluginFn = om.MFnPlugin(plugin, vendor, version)
    try:
        pluginFn.registerNode(RayIntersector.kNodeName, RayIntersector.kNodeId, 
                              RayIntersector.creator, RayIntersector.initialize, om.MPxNode.kDependNode)
        pluginFn.registerCommand(RaySceneIntersectorCommand.kCommandName, RaySceneIntersectorCommand.creator, RaySceneIntersectorCommand.syntaxCreator)
    except:
        om.MGlobal.displayError(f"Failed to register node: {RayIntersector.kNodeName} or command: {RaySceneIntersectorCommand.kCommandName}")
        raise

def uninitializePlugin(plugin):
    pluginFn = om.MFnPlugin(plugin)
    try:
        pluginFn.deregisterNode(RayIntersector.kNodeId)
        pluginFn.deregisterCommand(RaySceneIntersectorCommand.kCommandName)
    except:
        om.MGlobal.displayError(f"Failed to deregister node: {RayIntersector.kNodeName} or command: {RaySceneIntersectorCommand.kCommandName}")
        raise