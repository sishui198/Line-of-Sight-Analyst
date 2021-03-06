# coding=utf-8
import math
import arcpy
import functions_validation as fv
import functions_visibility as visibility
import functions_arcmap as farcmap


class AnalyseLoS(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Analyse Lines of Sight"
        self.description = "A tool for analysing Lines of Sight between observer and target points."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Lines of Sight",
            name="in_los",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["Polyline"]

        param1 = arcpy.Parameter(
            displayName="Observer points offset",
            name="in_observer_offset",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        # param1.filter.list = ["Double"]
        # param1.parameterDependencies = [param0.name]
        param1.enabled = 0

        param2 = arcpy.Parameter(
            displayName="Target points offset",
            name="in_target_offset",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        # param2.filter.list = ["Double"]
        # param2.parameterDependencies = [param0.name]
        param2.enabled = 0

        param3 = arcpy.Parameter(
            displayName="Object size",
            name="in_object_size",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            category="Fuzzy visibility")
        param3.value = 10

        param4 = arcpy.Parameter(
            displayName="Recognition acuinty",
            name="in_recognition_acuinty",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            category="Fuzzy visibility")
        param4.value = 0.017

        param5 = arcpy.Parameter(
            displayName="Clear visibility distance limit",
            name="in_clear_visibility_distance",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            category="Fuzzy visibility")
        param5.value = 500

        param6 = arcpy.Parameter(
            displayName="Use earth curvature and refraction corrections?",
            name="in_use_curvature",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input",
            category="Curvature corrections")
        param6.value = True

        param7 = arcpy.Parameter(
            displayName="Refractivity coefficient ",
            name="in_ref_coeff",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            category="Curvature corrections")
        param7.value = 0.13


        params = [param0, param1, param2, param3, param4, param5, param6, param7]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        fv.enableParamIfLine(parameters, 0, 1)
        fv.enableParamIfLine(parameters, 0, 2)

        if parameters[0].value:
            fv.fillParamaterWithFieldTypeAndDefaultFieldIfExists(parameters, 1, parameters[0].valueAsText,
                                                           "Double", "observ_offset")
            fv.fillParamaterWithFieldTypeAndDefaultFieldIfExists(parameters, 2, parameters[0].valueAsText,
                                                           "Double", "target_offset")

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        fv.checkProjected(parameters, 0)

        if parameters[0].value:
            message = "The input layer has fields typical for Global Sight Line. This analysis should be performed on " \
                      "Local Sight Lines. Are you sure you want to proceed?"
            fieldnames = [field.name for field in arcpy.ListFields(parameters[0].value)]

            if "target_x" in fieldnames and "target_y" in fieldnames:
                parameters[1].setWarningMessage(message)
                parameters[2].setWarningMessage(message)
            else:
                parameters[1].clearMessage()
                parameters[2].clearMessage()
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        visibility_lines = parameters[0].valueAsText
        observer_offset_field = parameters[1].valueAsText
        target_offset_field = parameters[2].valueAsText
        self.b1 = float(parameters[5].valueAsText)
        self.h = float(parameters[3].valueAsText)
        self.beta = parameters[4].value

        useCurvatures = parameters[6].value
        refCoeff = parameters[7].value


        fieldsNew = [ ("Visible", "Visibility of target", "SHORT"),
                       ("ViewAngle", "Viewing angle of target", "DOUBLE"),
                       ("ElevDiff", "Elevation difference of observer and target", "DOUBLE"),
                       ("AngleDiff_H", "Angle difference of target to horizon", "DOUBLE"),
                       ("ElevDiff_H", "Elevation difference of target to horizon", "DOUBLE"),
                       ("SlopeDiff", "Difference of target viewing angle to LoS slope", "DOUBLE"),
                       ("Horizon_C", "Horizon count", "SHORT"),
                       ("HorDist", "Distance of horizon from observer", "DOUBLE"),
                       ("FuzzyVis", "Fuzzy visibility", "DOUBLE")]

        fieldsNames = [row[0] for row in fieldsNew]

        columns = ["OBJECTID", "SHAPE@"] + [observer_offset_field, target_offset_field]

        farcmap.prepareDataColumns(visibility_lines, fieldsNew)

        number_of_LoS = int(arcpy.GetCount_management(visibility_lines).getOutput(0))

        arcpy.SetProgressor("step", "Analyzing " + str(number_of_LoS) + " lines of sight...", 0, number_of_LoS, 1)

        with arcpy.da.UpdateCursor(visibility_lines, columns + fieldsNames) as cursor:
            for row in cursor:

                points = []
                poi = visibility.WKTtoPoints(row[1].WKT)
                # get coordinates of first point for distance calculation

                observer_offset = row[2]
                target_offset = row[3]

                start_point_x = float(poi[0].split(" ")[0])
                start_point_y = float(poi[0].split(" ")[1])
                observer_elev = float(poi[0].split(" ")[2]) + observer_offset

                # for every point do this
                for i in range(0, len(poi)):
                    parts = poi[i].split(" ")
                    x = float(parts[0])
                    y = float(parts[1])
                    z = float(parts[2])
                    dist = visibility.distance(x, y, start_point_x, start_point_y)

                    if useCurvatures:
                        z = visibility.curvatureCorrections(z, dist, refCoeff)

                    if i == 0:
                        points.append([x, y, 0, observer_elev, -90])
                    elif i == len(poi) - 1:
                        points.append([x, y, dist, z + target_offset, visibility.angle(dist, z + target_offset - observer_elev)])
                    else:
                        points.append([x, y, dist, z, visibility.angle(dist, z - observer_elev)])

                results = self.analyzeLoS(points)
                for i in range(0, len(results)):
                    row[i + 4] = results[i]
                cursor.updateRow(row)
                arcpy.SetProgressorPosition()

        arcpy.ResetProgressor()

        return

    def analyzeLoS(self, points):
        limit_angle = points[len(points) - 1][4]
        isVisible = 1
        max_angle_horizon = - 180
        elev_difference_horizon = None
        angle_difference_horizon = None
        slope_LoS_diffence = None
        fuzzy_visibility = None
        elev_diff = points[0][3] - points[len(points) - 1][3]
        horizon_count = 0
        horizon_distance = 0

        for i in range(1, len(points) - 1):
            if points[i][4] > limit_angle:
                isVisible = 0  # False
            if visibility.isHorizon(points, i, 4, limit_angle) and points[i][4] > max_angle_horizon:
                max_angle_horizon = points[i][4]
                horizon_count += 1
                horizon_distance = points[i][3]

        elev_difference_horizon = points[len(points) - 1][3] - points[0][3] - math.tan(
            math.radians(max_angle_horizon)) * points[len(points) - 1][2]
        angle_difference_horizon = limit_angle - max_angle_horizon
        slope_LoS_diffence = math.degrees(math.atan((points[len(points) - 1][3] - points[len(points) - 2][3]) / (
        points[len(points) - 1][2] - points[len(points) - 2][2]))) - limit_angle
        fuzzy_visibility = visibility.fuzzyVisibility(points[len(points) - 1][2], self.b1, self.beta, self.h)

        return [isVisible, limit_angle, elev_diff, angle_difference_horizon, elev_difference_horizon,
                slope_LoS_diffence, horizon_count, horizon_distance, fuzzy_visibility]
