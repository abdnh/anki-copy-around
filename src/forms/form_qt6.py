# Form implementation generated from reading ui file 'designer/form.ui'
#
# Created by: PyQt6 UI code generator 6.2.3
#
# WARNING: Any manual changes made to this file will be lost when pyuic6 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(512, 327)
        self.formLayout_2 = QtWidgets.QFormLayout(Dialog)
        self.formLayout_2.setObjectName("formLayout_2")
        self.label_5 = QtWidgets.QLabel(Dialog)
        self.label_5.setObjectName("label_5")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_5)
        self.searchFieldComboBox = QtWidgets.QComboBox(Dialog)
        self.searchFieldComboBox.setObjectName("searchFieldComboBox")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.ItemRole.FieldRole, self.searchFieldComboBox)
        self.label_6 = QtWidgets.QLabel(Dialog)
        self.label_6.setObjectName("label_6")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_6)
        self.copyIntoFieldComboBox = QtWidgets.QComboBox(Dialog)
        self.copyIntoFieldComboBox.setObjectName("copyIntoFieldComboBox")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.ItemRole.FieldRole, self.copyIntoFieldComboBox)
        self.label_2 = QtWidgets.QLabel(Dialog)
        self.label_2.setObjectName("label_2")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_2)
        self.notetypeChooser = QtWidgets.QWidget(Dialog)
        self.notetypeChooser.setObjectName("notetypeChooser")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.ItemRole.FieldRole, self.notetypeChooser)
        self.label_4 = QtWidgets.QLabel(Dialog)
        self.label_4.setObjectName("label_4")
        self.formLayout_2.setWidget(4, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_4)
        self.matchedNotesLimitCheckBox = QtWidgets.QCheckBox(Dialog)
        self.matchedNotesLimitCheckBox.setObjectName("matchedNotesLimitCheckBox")
        self.formLayout_2.setWidget(6, QtWidgets.QFormLayout.ItemRole.LabelRole, self.matchedNotesLimitCheckBox)
        self.matchedNotesSpinBox = QtWidgets.QSpinBox(Dialog)
        self.matchedNotesSpinBox.setEnabled(False)
        self.matchedNotesSpinBox.setMinimum(1)
        self.matchedNotesSpinBox.setObjectName("matchedNotesSpinBox")
        self.formLayout_2.setWidget(6, QtWidgets.QFormLayout.ItemRole.FieldRole, self.matchedNotesSpinBox)
        self.copyButton = QtWidgets.QPushButton(Dialog)
        self.copyButton.setObjectName("copyButton")
        self.formLayout_2.setWidget(8, QtWidgets.QFormLayout.ItemRole.FieldRole, self.copyButton)
        self.searchInFieldCheckBox = QtWidgets.QCheckBox(Dialog)
        self.searchInFieldCheckBox.setObjectName("searchInFieldCheckBox")
        self.formLayout_2.setWidget(3, QtWidgets.QFormLayout.ItemRole.LabelRole, self.searchInFieldCheckBox)
        self.searchInFieldComboBox = QtWidgets.QComboBox(Dialog)
        self.searchInFieldComboBox.setEnabled(False)
        self.searchInFieldComboBox.setObjectName("searchInFieldComboBox")
        self.formLayout_2.setWidget(3, QtWidgets.QFormLayout.ItemRole.FieldRole, self.searchInFieldComboBox)
        self.randomizeCheckBox = QtWidgets.QCheckBox(Dialog)
        self.randomizeCheckBox.setObjectName("randomizeCheckBox")
        self.formLayout_2.setWidget(7, QtWidgets.QFormLayout.ItemRole.SpanningRole, self.randomizeCheckBox)
        self.copyFromListWidget = QtWidgets.QListWidget(Dialog)
        self.copyFromListWidget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.copyFromListWidget.setObjectName("copyFromListWidget")
        self.formLayout_2.setWidget(4, QtWidgets.QFormLayout.ItemRole.FieldRole, self.copyFromListWidget)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)
        Dialog.setTabOrder(self.searchFieldComboBox, self.copyIntoFieldComboBox)
        Dialog.setTabOrder(self.copyIntoFieldComboBox, self.matchedNotesLimitCheckBox)
        Dialog.setTabOrder(self.matchedNotesLimitCheckBox, self.matchedNotesSpinBox)
        Dialog.setTabOrder(self.matchedNotesSpinBox, self.copyButton)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Dialog"))
        self.label_5.setText(_translate("Dialog", "Field to search for"))
        self.label_6.setText(_translate("Dialog", "Field to copy into"))
        self.label_2.setText(_translate("Dialog", "Notetype to search"))
        self.label_4.setText(_translate("Dialog", "Fields to leech from"))
        self.matchedNotesLimitCheckBox.setText(_translate("Dialog", "Limit matched notes"))
        self.copyButton.setText(_translate("Dialog", "Copy"))
        self.searchInFieldCheckBox.setText(_translate("Dialog", "Field to search in"))
        self.randomizeCheckBox.setText(_translate("Dialog", "Randomize results"))
