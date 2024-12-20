from pynetdicom.presentation import (
    build_context,
)

# Prebuilt context matching the DCMTK Implementation https://github.com/DCMTK/dcmtk/blob/d1fb197927fd4178b5a24e0f0dba6f8d785a8f93/dcmdata/libsrc/dcuid.cc#L895
_storage = [
    "1.2.840.10008.5.1.4.1.1.9.1.3",  # AmbulatoryECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.9.5.1",  # ArterialPulseWaveformStorage
    "1.2.840.10008.5.1.4.1.1.78.2",  # AutorefractionMeasurementsStorage
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
    "1.2.840.10008.5.1.4.1.1.88.70",  # ImplantationPlanSRStorage
    "1.2.840.10008.5.1.4.1.1.78.8",  # IntraocularLensCalculationsStorage
    "1.2.840.10008.5.1.4.1.1.14.1",  # IntravascularOpticalCoherenceTomographyImageStorageForPresentation # noqa: E501
    "1.2.840.10008.5.1.4.1.1.14.2",  # IntravascularOpticalCoherenceTomographyImageStorageForProcessing # noqa: E501
    "1.2.840.10008.5.1.4.1.1.78.3",  # KeratometryMeasurementsStorage
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
    "1.2.840.10008.5.1.4.1.1.78.4",  # SubjectiveRefractionMeasurementsStorage
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
    "1.2.840.10008.5.1.4.1.1.77.1.3",  # VLSlideCoordinatesMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.6",  # VLWholeSlideMicroscopyImageStorage
    "1.2.840.10008.5.1.4.1.1.11.5",  # XAXRFGrayscaleSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.13.1.1",  # XRay3DAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.13.1.2",  # XRay3DCraniofacialImageStorage
    "1.2.840.10008.5.1.4.1.1.12.1",  # XRayAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.88.67",  # XRayRadiationDoseSRStorage
    "1.2.840.10008.5.1.4.1.1.12.2",  # XRayRadiofluoroscopicImageStorage
    ## retired but still in use
    "1.2.840.10008.5.1.1.30",  # HardcopyColorImageStorage
    "1.2.840.10008.5.1.1.29",  # HardcopyGrayscaleImageStorage
    "1.2.840.10008.5.1.4.1.1.5",  # NuclearMedicineImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.9",  # StandaloneCurveStorage
    "1.2.840.10008.5.1.4.1.1.10",  # StandaloneModalityLUTStorage
    "1.2.840.10008.5.1.4.1.1.8",  # StandaloneOverlayStorage
    "1.2.840.10008.5.1.4.1.1.129",  # StandalonePETCurveStorage
    "1.2.840.10008.5.1.4.1.1.11",  # StandaloneVOILUTStorage
    "1.2.840.10008.5.1.1.27",  # StoredPrintStorage
    "1.2.840.10008.5.1.4.1.1.6",  # UltrasoundImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.3",  # UltrasoundMultiframeImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.77.1",  # VLImageStorage
    "1.2.840.10008.5.1.4.1.1.77.2",  # VLMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.12.3",  # XRayAngiographicBiPlaneImageStorage
]
assert len(_storage) <= 120

StoragePresentationContexts = [build_context(uid) for uid in sorted(_storage)]
"""Pre-built presentation contexts for :dcm:`Storage<part04/chapter_B.html>` containing 120 selected SOP Classes."""  # noqa: E501
