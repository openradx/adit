from pynetdicom.presentation import (
    build_context,
)


# Prebuilt context matching the DCMTK Implementation https://github.com/DCMTK/dcmtk/blob/d1fb197927fd4178b5a24e0f0dba6f8d785a8f93/dcmdata/libsrc/dcuid.cc#L895
_storage = [
    "1.2.840.10008.5.1.4.1.1.9.1.3",  # AmbulatoryECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.9.5.1",  # ArterialPulseWaveformStorage
    "1.2.840.10008.5.1.4.1.1.78.4",  # AutorefractionMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.131",  # BasicStructuredDisplayStorage
    "1.2.840.10008.5.1.4.1.1.88.11",  # BasicTextSRStorage
    "1.2.840.10008.5.1.4.1.1.9.4.1",  # BasicVoiceAudioWaveformStorage
    "1.2.840.10008.5.1.4.1.1.11.4",  # BlendingSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.13.1.3",  # BreastTomosynthesisImageStorage
    "1.2.840.10008.5.1.4.1.1.9.3.1",  # CardiacElectrophysiologyWaveformStorage
    "1.2.840.10008.5.1.4.1.1.88.65",  # ChestCADSRStorage
    "1.2.840.10008.5.1.4.1.1.88.69",  # ColonCADSRStorage
    "1.2.840.10008.5.1.4.1.1.11.2",  # ColorSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.88.34",  # Comprehensive3DSRStorage
    "1.2.840.10008.5.1.4.1.1.88.33",  # ComprehensiveSRStorage
    "1.2.840.10008.5.1.4.1.1.1",  # ComputedRadiographyImageStorage
    "1.2.840.10008.5.1.4.1.1.2",  # CTImageStorage
    "1.2.840.10008.5.1.4.1.1.66.3",  # DeformableSpatialRegistrationStorage
    "1.2.840.10008.5.1.4.1.1.1.3",  # DigitalIntraOralXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.3.1",  # DigitalIntraOralXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.1.2",  # DigitalMammographyXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.2.1",  # DigitalMammographyXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.1.1",  # DigitalXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.1.1",  # DigitalXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.104.2",  # EncapsulatedCDAStorage
    "1.2.840.10008.5.1.4.1.1.104.1",  # EncapsulatedPDFStorage
    "1.2.840.10008.5.1.4.1.1.2.1",  # EnhancedCTImageStorage
    "1.2.840.10008.5.1.4.1.1.4.3",  # EnhancedMRColorImageStorage
    "1.2.840.10008.5.1.4.1.1.4.1",  # EnhancedMRImageStorage
    "1.2.840.10008.5.1.4.1.1.130",  # EnhancedPETImageStorage
    "1.2.840.10008.5.1.4.1.1.88.22",  # EnhancedSRStorage
    "1.2.840.10008.5.1.4.1.1.6.2",  # EnhancedUSVolumeStorage
    "1.2.840.10008.5.1.4.1.1.12.1.1",  # EnhancedXAImageStorage
    "1.2.840.10008.5.1.4.1.1.12.2.1",  # EnhancedXRFImageStorage
    "1.2.840.10008.5.1.4.1.1.9.4.2",  # GeneralAudioWaveformStorage
    "1.2.840.10008.5.1.4.1.1.9.1.2",  # GeneralECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.11.1",  # GrayscaleSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.9.2.1",  # HemodynamicWaveformStorage
    "1.2.840.10008.5.1.4.1.1.88.68",  # ImplantationPlanSRStorage
    "1.2.840.10008.5.1.4.1.1.78.8",  # IntraocularLensCalculationsStorage
    "1.2.840.10008.5.1.4.1.1.14.1",  # IntravascularOpticalCoherenceTomographyImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.14.2",  # IntravascularOpticalCoherenceTomographyImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.78.2",  # KeratometryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.88.59",  # KeyObjectSelectionDocumentStorage
    "1.2.840.10008.5.1.4.1.1.2.2",  # LegacyConvertedEnhancedCTImageStorage
    "1.2.840.10008.5.1.4.1.1.4.4",  # LegacyConvertedEnhancedMRImageStorage
    "1.2.840.10008.5.1.4.1.1.128.1",  # LegacyConvertedEnhancedPETImageStorage
    "1.2.840.10008.5.1.4.1.1.78.1",  # LensometryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.79.1",  # MacularGridThicknessAndVolumeReportStorage
    "1.2.840.10008.5.1.4.1.1.88.50",  # MammographyCADSRStorage
    "1.2.840.10008.5.1.4.1.1.4",  # MRImageStorage
    "1.2.840.10008.5.1.4.1.1.4.2",  # MRSpectroscopyStorage
    "1.2.840.10008.5.1.4.1.1.7.2",  # MultiframeGrayscaleByteSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.3",  # MultiframeGrayscaleWordSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.1",  # MultiframeSingleBitSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.4",  # MultiframeTrueColorSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.20",  # NuclearMedicineImageStorage
    "1.2.840.10008.5.1.4.1.1.78.7",  # OphthalmicAxialMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.2",  # OphthalmicPhotography16BitImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.1",  # OphthalmicPhotography8BitImageStorage
    "1.2.840.10008.5.1.4.1.1.81.1",  # OphthalmicThicknessMapStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.4",  # OphthalmicTomographyImageStorage
    "1.2.840.10008.5.1.4.1.1.80.1",  # OphthalmicVisualFieldStaticPerimetryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.128",  # PositronEmissionTomographyImageStorage
    "1.2.840.10008.5.1.4.1.1.88.40",  # ProcedureLogStorage
    "1.2.840.10008.5.1.4.1.1.11.3",  # PseudoColorSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.66",  # RawDataStorage
    "1.2.840.10008.5.1.4.1.1.67",  # RealWorldValueMappingStorage
    "1.2.840.10008.5.1.4.1.1.9.6.1",  # RespiratoryWaveformStorage
    "1.2.840.10008.5.1.4.34.7",  # RTBeamsDeliveryInstructionStorage
    "1.2.840.10008.5.1.4.1.1.481.4",  # RTBeamsTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.6",  # RTBrachyTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.2",  # RTDoseStorage
    "1.2.840.10008.5.1.4.1.1.481.1",  # RTImageStorage
    "1.2.840.10008.5.1.4.1.1.481.9",  # RTIonBeamsTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.8",  # RTIonPlanStorage
    "1.2.840.10008.5.1.4.1.1.481.5",  # RTPlanStorage
    "1.2.840.10008.5.1.4.1.1.481.3",  # RTStructureSetStorage
    "1.2.840.10008.5.1.4.1.1.481.7",  # RTTreatmentSummaryRecordStorage
    "1.2.840.10008.5.1.4.1.1.7",  # SecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.66.4",  # SegmentationStorage
    "1.2.840.10008.5.1.4.1.1.66.2",  # SpatialFiducialsStorage
    "1.2.840.10008.5.1.4.1.1.66.1",  # SpatialRegistrationStorage
    "1.2.840.10008.5.1.4.1.1.78.6",  # SpectaclePrescriptionReportStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.3",  # StereometricRelationshipStorage
    "1.2.840.10008.5.1.4.1.1.78.3",  # SubjectiveRefractionMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.68.1",  # SurfaceScanMeshStorage
    "1.2.840.10008.5.1.4.1.1.68.2",  # SurfaceScanPointCloudStorage
    "1.2.840.10008.5.1.4.1.1.66.5",  # SurfaceSegmentationStorage
    "1.2.840.10008.5.1.4.1.1.9.1.1",  # TwelveLeadECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.6.1",  # UltrasoundImageStorage
    "1.2.840.10008.5.1.4.1.1.3.1",  # UltrasoundMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.1.1",  # VideoEndoscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.2.1",  # VideoMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.4.1",  # VideoPhotographicImageStorage
    "1.2.840.10008.5.1.4.1.1.78.5",  # VisualAcuityMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.77.1.1",  # VLEndoscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.2",  # VLMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.4",  # VLPhotographicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.1",  # VLSlideCoordinatesMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.6",  # VLWholeSlideMicroscopyImageStorage
    "1.2.840.10008.5.1.4.1.1.11.5",  # XAXRFGrayscaleSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.13.1.1",  # XRay3DAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.13.1.2",  # XRay3DCraniofacialImageStorage
    "1.2.840.10008.5.1.4.1.1.12.1",  # XRayAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.88.67",  # XRayRadiationDoseSRStorage
    "1.2.840.10008.5.1.4.1.1.12.2",  # XRayRadiofluoroscopicImageStorage
    ## recently approved
    # "1.2.840.10008.5.1.4.1.1.88.74",  # AcquisitionContextSRStorage
    # "1.2.840.10008.5.1.4.1.1.11.8",  # AdvancedBlendingPresentationStateStorage
    # "1.2.840.10008.5.1.4.1.1.9.8.1",  # BodyPositionWaveformStorage
    # "1.2.840.10008.5.1.4.1.1.1.2.2",  # BreastProjectionXRayImageStorageForPresentation
    # "1.2.840.10008.5.1.4.1.1.1.2.3",  # BreastProjectionXRayImageStorageForProcessing
    # "1.2.840.10008.5.1.4.1.1.481.22",  # CArmPhotonElectronRadiationRecordStorage
    # "1.2.840.10008.5.1.4.1.1.481.21",  # CArmPhotonElectronRadiationStorage
    # "1.2.840.10008.5.1.4.1.1.11.7",  # CompositingPlanarMPRVolumetricPresentationStateStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.8",  # ConfocalMicroscopyImageStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.9",  # ConfocalMicroscopyTiledPyramidalImageStorage
    # "1.2.840.10008.5.1.4.1.1.88.73",  # ContentAssessmentResultsStorage
    # "1.2.840.10008.5.1.4.1.1.82.1",  # CornealTopographyMapStorage
    # "1.2.840.10008.5.1.4.1.1.200.2",  # CTPerformedProcedureProtocolStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.7",  # DermoscopicPhotographyImageStorage
    # "1.2.840.10008.5.1.4.1.1.9.7.2",  # ElectromyogramWaveformStorage
    # "1.2.840.10008.5.1.4.1.1.9.7.3",  # ElectrooculogramWaveformStorage
    # "1.2.840.10008.5.1.4.1.1.104.5",  # EncapsulatedMTLStorage
    # "1.2.840.10008.5.1.4.1.1.104.4",  # EncapsulatedOBJStorage
    # "1.2.840.10008.5.1.4.1.1.104.3",  # EncapsulatedSTLStorage
    # "1.2.840.10008.5.1.4.1.1.481.16",  # EnhancedContinuousRTImageStorage
    # "1.2.840.10008.5.1.4.1.1.481.15",  # EnhancedRTImageStorage
    # "1.2.840.10008.5.1.4.1.1.88.76",  # EnhancedXRayRadiationDoseSRStorage
    # "1.2.840.10008.5.1.4.1.1.88.35",  # ExtensibleSRStorage
    # "1.2.840.10008.5.1.4.1.1.9.1.4",  # General32BitECGWaveformStorage
    # "1.2.840.10008.5.1.4.1.1.11.6",  # GrayscalePlanarMPRVolumetricPresentationStateStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.10",  # MicroscopyBulkSimpleAnnotationsStorage
    # "1.2.840.10008.5.1.4.1.1.9.6.2",  # MultichannelRespiratoryWaveformStorage
    # "1.2.840.10008.5.1.4.1.1.11.11",  # MultipleVolumeRenderingVolumetricPresentationStateStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.5.8",  # OphthalmicOpticalCoherenceTomographyBscanVolumeAnalysisStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.5.7",  # OphthalmicOpticalCoherenceTomographyEnFaceImageStorage
    # "1.2.840.10008.5.1.4.1.1.30",  # ParametricMapStorage
    # "1.2.840.10008.5.1.4.1.1.88.72",  # PatientRadiationDoseSRStorage
    # "1.2.840.10008.5.1.4.1.1.88.75",  # PerformedImagingAgentAdministrationSRStorage
    # "1.2.840.10008.5.1.4.1.1.6.3",  # PhotoacousticImageStorage
    # "1.2.840.10008.5.1.4.1.1.88.77",  # PlannedImagingAgentAdministrationSRStorage
    # "1.2.840.10008.5.1.4.1.1.88.71",  # RadiopharmaceuticalRadiationDoseSRStorage
    # "1.2.840.10008.5.1.4.1.1.481.25",  # RoboticArmRadiationStorage
    # "1.2.840.10008.5.1.4.1.1.481.26",  # RoboticRadiationRecordStorage
    # "1.2.840.10008.5.1.4.1.1.9.7.1",  # RoutineScalpElectroencephalogramWaveformStorage
    # "1.2.840.10008.5.1.4.34.10",  # RTBrachyApplicationSetupDeliveryInstructionStorage
    # "1.2.840.10008.5.1.4.34.9",  # RTPatientPositionAcquisitionInstructionStorage
    # "1.2.840.10008.5.1.4.1.1.481.10",  # RTPhysicianIntentStorage
    # "1.2.840.10008.5.1.4.1.1.481.14",  # RTRadiationRecordSetStorage
    # "1.2.840.10008.5.1.4.1.1.481.13",  # RTRadiationSalvageRecordStorage
    # "1.2.840.10008.5.1.4.34.8",  # RTRadiationSetDeliveryInstructionStorage
    # "1.2.840.10008.5.1.4.1.1.481.12",  # RTRadiationSetStorage
    # "1.2.840.10008.5.1.4.1.1.481.11",  # RTSegmentAnnotationStorage
    # "1.2.840.10008.5.1.4.1.1.481.17",  # RTTreatmentPreparationStorage
    # "1.2.840.10008.5.1.4.1.1.11.10",  # SegmentedVolumeRenderingVolumetricPresentationStateStorage
    # "1.2.840.10008.5.1.4.1.1.88.78",  # SimplifiedAdultEchoSRStorage
    # "1.2.840.10008.5.1.4.1.1.9.7.4",  # SleepElectroencephalogramWaveformStorage
    # "1.2.840.10008.5.1.4.1.1.481.24",  # TomotherapeuticRadiationRecordStorage
    # "1.2.840.10008.5.1.4.1.1.481.23",  # TomotherapeuticRadiationStorage
    # "1.2.840.10008.5.1.4.1.1.66.6",  # TractographyResultsStorage
    # "1.2.840.10008.5.1.4.1.1.11.12",  # VariableModalityLUTSoftcopyPresentationStateStorage
    # "1.2.840.10008.5.1.4.1.1.11.9",  # VolumeRenderingVolumetricPresentationStateStorage
    # "1.2.840.10008.5.1.4.1.1.88.70",  # WaveformAnnotationSRStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.5.5",  # WideFieldOphthalmicPhotographyStereographicProjectionImageStorage
    # "1.2.840.10008.5.1.4.1.1.77.1.5.6",  # WideFieldOphthalmicPhotography3DCoordinatesImageStorage
    # "1.2.840.10008.5.1.4.1.1.200.8"  # XAPerformedProcedureProtocolStorage
    ## non-patient
    # "1.2.840.10008.5.1.4.39.2",  # ColorPaletteStorage
    # "1.2.840.10008.5.1.4.1.1.200.1",  # CTDefinedProcedureProtocolStorage  
    # "1.2.840.10008.5.1.4.43.1",  # GenericImplantTemplateStorage
    # "1.2.840.10008.5.1.4.38.1",  # HangingProtocolStorage
    # "1.2.840.10008.5.1.4.44.1",  # ImplantAssemblyTemplateStorage
    # "1.2.840.10008.5.1.4.45.1",  # ImplantTemplateGroupStorage
    # "1.2.840.10008.5.1.4.1.1.201.1",  # InventoryStorage
    # "1.2.840.10008.5.1.4.1.1.200.3",  # ProtocolApprovalStorage
    # "1.2.840.10008.5.1.4.1.1.200.7",  # XADefinedProcedureProtocolStorage
    ## retired
    "1.2.840.10008.5.1.4.1.1.30",  # RETIRED_HardcopyColorImageStorage
    "1.2.840.10008.5.1.4.1.1.29",  # RETIRED_HardcopyGrayscaleImageStorage
    "1.2.840.10008.5.1.4.1.1.5",  # RETIRED_NuclearMedicineImageStorage
    "1.2.840.10008.5.1.4.1.1.9",  # RETIRED_StandaloneCurveStorage
    "1.2.840.10008.5.1.4.1.1.10",  # RETIRED_StandaloneModalityLUTStorage
    "1.2.840.10008.5.1.4.1.1.8",  # RETIRED_StandaloneOverlayStorage
    "1.2.840.10008.5.1.4.1.1.129",  # RETIRED_StandalonePETCurveStorage
    "1.2.840.10008.5.1.4.1.1.11",  # RETIRED_StandaloneVOILUTStorage
    "1.2.840.10008.5.1.4.1.1.27",  # RETIRED_StoredPrintStorage
    "1.2.840.10008.5.1.4.1.1.6",  # RETIRED_UltrasoundImageStorage
    "1.2.840.10008.5.1.4.1.1.3",  # RETIRED_UltrasoundMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1",  # RETIRED_VLImageStorage
    "1.2.840.10008.5.1.4.1.1.77.2",  # RETIRED_VLMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.12.3",  # RETIRED_XRayAngiographicBiPlaneImageStorage
    ## draft
    # "1.2.840.10008.5.1.4.34.7",  # DRAFT_RTBeamsDeliveryInstructionStorage
    # "1.2.840.10008.5.1.4.1.1.88.2",  # DRAFT_SRAudioStorage
    # "1.2.840.10008.5.1.4.1.1.88.3",  # DRAFT_SRComprehensiveStorage
    # "1.2.840.10008.5.1.4.1.1.88.4",  # DRAFT_SRDetailStorage
    # "1.2.840.10008.5.1.4.1.1.88.5",  # DRAFT_SRTextStorage
    # "1.2.840.10008.5.1.4.1.1.9.1",  # DRAFT_WaveformStorage
    ## DICOS
    # "1.2.840.10008.5.1.4.1.1.501.1",  # DICOS_CTImageStorage
    # "1.2.840.10008.5.1.4.1.1.501.2.1",  # DICOS_DigitalXRayImageStorageForPresentation
    # "1.2.840.10008.5.1.4.1.1.501.2.2",  # DICOS_DigitalXRayImageStorageForProcessing
    # "1.2.840.10008.5.1.4.1.1.501.3",  # DICOS_ThreatDetectionReportStorage
    # "1.2.840.10008.5.1.4.1.1.501.4",  # DICOS_2DAITStorage
    # "1.2.840.10008.5.1.4.1.1.501.5",  # DICOS_3DAITStorage
    # "1.2.840.10008.5.1.4.1.1.501.6",  # DICOS_QuadrupoleResonanceStorage
    ## DICONDE
    # "1.2.840.10008.5.1.4.1.1.601.1",  # DICONDE_EddyCurrentImageStorage
    # "1.2.840.10008.5.1.4.1.1.601.2",  # DICONDE_EddyCurrentMultiframeImageStorage
]

assert len(_storage) <= 128

AditStoragePresentationContexts = [build_context(uid) for uid in sorted(_storage)]
"""Pre-built presentation contexts for :dcm:`Storage<part04/chapter_B.html>` matching the DCMTK Implementation."""
