from pynetdicom.presentation import (
    build_context,
)

_uncompressed_transfer_syntaxes = [
    "1.2.840.10008.1.2",        # Implicit VR Little Endian
    "1.2.840.10008.1.2.1",      # Explicit VR Little Endian
]

_compressed_transfer_syntaxes = [
    "1.2.840.10008.1.2.4.50",   # JPEG Baseline
    "1.2.840.10008.1.2.4.51",   # JPEG Extended
    "1.2.840.10008.1.2.4.57",   # JPEG Lossless
    "1.2.840.10008.1.2.4.70",   # JPEG Lossless SV1 (default for most PACS)
    "1.2.840.10008.1.2.4.80",   # JPEG-LS Lossless
    "1.2.840.10008.1.2.4.81",   # JPEG-LS Near Lossless
    "1.2.840.10008.1.2.4.90",   # JPEG 2000 Lossless
    "1.2.840.10008.1.2.4.91",   # JPEG 2000
    "1.2.840.10008.1.2.5",      # RLE Lossless
]

# Image SOP classes contain pixel data and may be stored in compressed transfer
# syntaxes.  We offer both compressed and uncompressed so the SCP can pick
# whichever matches its internal storage.
_image_storage = [
    "1.2.840.10008.5.1.4.1.1.13.1.3",  # BreastTomosynthesisImageStorage
    "1.2.840.10008.5.1.4.1.1.1",        # ComputedRadiographyImageStorage
    "1.2.840.10008.5.1.4.1.1.2",        # CTImageStorage
    "1.2.840.10008.5.1.4.1.1.1.3",      # DigitalIntraOralXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.3.1",    # DigitalIntraOralXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.1.2",      # DigitalMammographyXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.2.1",    # DigitalMammographyXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.1.1",      # DigitalXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.1.1",    # DigitalXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.2.1",      # EnhancedCTImageStorage
    "1.2.840.10008.5.1.4.1.1.4.3",      # EnhancedMRColorImageStorage
    "1.2.840.10008.5.1.4.1.1.4.1",      # EnhancedMRImageStorage
    "1.2.840.10008.5.1.4.1.1.130",      # EnhancedPETImageStorage
    "1.2.840.10008.5.1.4.1.1.6.2",      # EnhancedUSVolumeStorage
    "1.2.840.10008.5.1.4.1.1.12.1.1",   # EnhancedXAImageStorage
    "1.2.840.10008.5.1.4.1.1.12.2.1",   # EnhancedXRFImageStorage
    "1.2.840.10008.5.1.4.1.1.14.1",     # IntravascularOpticalCoherenceTomographyImageStorageForPresentation # noqa: E501
    "1.2.840.10008.5.1.4.1.1.14.2",     # IntravascularOpticalCoherenceTomographyImageStorageForProcessing # noqa: E501
    "1.2.840.10008.5.1.4.1.1.2.2",      # LegacyConvertedEnhancedCTImageStorage
    "1.2.840.10008.5.1.4.1.1.4.4",      # LegacyConvertedEnhancedMRImageStorage
    "1.2.840.10008.5.1.4.1.1.128.1",    # LegacyConvertedEnhancedPETImageStorage
    "1.2.840.10008.5.1.4.1.1.4",        # MRImageStorage
    "1.2.840.10008.5.1.4.1.1.7.2",      # MultiframeGrayscaleByteSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.3",      # MultiframeGrayscaleWordSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.1",      # MultiframeSingleBitSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.4",      # MultiframeTrueColorSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.20",       # NuclearMedicineImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.2", # OphthalmicPhotography16BitImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.1", # OphthalmicPhotography8BitImageStorage
    "1.2.840.10008.5.1.4.1.1.81.1",     # OphthalmicThicknessMapStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.4", # OphthalmicTomographyImageStorage
    "1.2.840.10008.5.1.4.1.1.128",      # PositronEmissionTomographyImageStorage
    "1.2.840.10008.5.1.4.1.1.481.1",    # RTImageStorage
    "1.2.840.10008.5.1.4.1.1.7",        # SecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.6.1",      # UltrasoundImageStorage
    "1.2.840.10008.5.1.4.1.1.3.1",      # UltrasoundMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.1.1", # VideoEndoscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.2.1", # VideoMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.4.1", # VideoPhotographicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.1",   # VLEndoscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.2",   # VLMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.4",   # VLPhotographicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.3",   # VLSlideCoordinatesMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.6",   # VLWholeSlideMicroscopyImageStorage
    "1.2.840.10008.5.1.4.1.1.13.1.1",   # XRay3DAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.13.1.2",   # XRay3DCraniofacialImageStorage
    "1.2.840.10008.5.1.4.1.1.12.1",     # XRayAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.12.2",     # XRayRadiofluoroscopicImageStorage
    ## retired but still in use
    "1.2.840.10008.5.1.1.30",           # HardcopyColorImageStorage
    "1.2.840.10008.5.1.1.29",           # HardcopyGrayscaleImageStorage
    "1.2.840.10008.5.1.4.1.1.5",        # NuclearMedicineImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.6",        # UltrasoundImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.3",        # UltrasoundMultiframeImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.77.1",     # VLImageStorage
    "1.2.840.10008.5.1.4.1.1.77.2",     # VLMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.12.3",     # XRayAngiographicBiPlaneImageStorage
]

# Non-image SOP classes: structured reports, waveforms, presentation states,
# raw data, registration, RT non-image, etc.  These do NOT contain pixel data
# and must NOT be offered with compressed transfer syntaxes.  If the SCP
# negotiates a compressed TS for these, it will fail when it tries to encode
# the non-pixel payload as JPEG.
_non_image_storage = [
    "1.2.840.10008.5.1.4.1.1.9.1.3",   # AmbulatoryECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.9.5.1",   # ArterialPulseWaveformStorage
    "1.2.840.10008.5.1.4.1.1.78.2",    # AutorefractionMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.131",     # BasicStructuredDisplayStorage
    "1.2.840.10008.5.1.4.1.1.88.11",   # BasicTextSRStorage
    "1.2.840.10008.5.1.4.1.1.9.4.1",   # BasicVoiceAudioWaveformStorage
    "1.2.840.10008.5.1.4.1.1.11.4",    # BlendingSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.9.3.1",   # CardiacElectrophysiologyWaveformStorage
    "1.2.840.10008.5.1.4.1.1.88.65",   # ChestCADSRStorage
    "1.2.840.10008.5.1.4.1.1.88.69",   # ColonCADSRStorage
    "1.2.840.10008.5.1.4.1.1.11.2",    # ColorSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.88.34",   # Comprehensive3DSRStorage
    "1.2.840.10008.5.1.4.1.1.88.33",   # ComprehensiveSRStorage
    "1.2.840.10008.5.1.4.1.1.66.3",    # DeformableSpatialRegistrationStorage
    "1.2.840.10008.5.1.4.1.1.104.2",   # EncapsulatedCDAStorage
    "1.2.840.10008.5.1.4.1.1.104.1",   # EncapsulatedPDFStorage
    "1.2.840.10008.5.1.4.1.1.88.22",   # EnhancedSRStorage
    "1.2.840.10008.5.1.4.1.1.9.4.2",   # GeneralAudioWaveformStorage
    "1.2.840.10008.5.1.4.1.1.9.1.2",   # GeneralECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.11.1",    # GrayscaleSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.9.2.1",   # HemodynamicWaveformStorage
    "1.2.840.10008.5.1.4.1.1.88.70",   # ImplantationPlanSRStorage
    "1.2.840.10008.5.1.4.1.1.78.8",    # IntraocularLensCalculationsStorage
    "1.2.840.10008.5.1.4.1.1.78.3",    # KeratometryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.88.59",   # KeyObjectSelectionDocumentStorage
    "1.2.840.10008.5.1.4.1.1.78.1",    # LensometryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.79.1",    # MacularGridThicknessAndVolumeReportStorage
    "1.2.840.10008.5.1.4.1.1.88.50",   # MammographyCADSRStorage
    "1.2.840.10008.5.1.4.1.1.4.2",     # MRSpectroscopyStorage
    "1.2.840.10008.5.1.4.1.1.78.7",    # OphthalmicAxialMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.80.1",    # OphthalmicVisualFieldStaticPerimetryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.88.40",   # ProcedureLogStorage
    "1.2.840.10008.5.1.4.1.1.11.3",    # PseudoColorSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.66",      # RawDataStorage
    "1.2.840.10008.5.1.4.1.1.67",      # RealWorldValueMappingStorage
    "1.2.840.10008.5.1.4.1.1.9.6.1",   # RespiratoryWaveformStorage
    "1.2.840.10008.5.1.4.34.7",        # RTBeamsDeliveryInstructionStorage
    "1.2.840.10008.5.1.4.1.1.481.4",   # RTBeamsTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.6",   # RTBrachyTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.2",   # RTDoseStorage
    "1.2.840.10008.5.1.4.1.1.481.9",   # RTIonBeamsTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.8",   # RTIonPlanStorage
    "1.2.840.10008.5.1.4.1.1.481.5",   # RTPlanStorage
    "1.2.840.10008.5.1.4.1.1.481.3",   # RTStructureSetStorage
    "1.2.840.10008.5.1.4.1.1.481.7",   # RTTreatmentSummaryRecordStorage
    "1.2.840.10008.5.1.4.1.1.66.4",    # SegmentationStorage
    "1.2.840.10008.5.1.4.1.1.66.2",    # SpatialFiducialsStorage
    "1.2.840.10008.5.1.4.1.1.66.1",    # SpatialRegistrationStorage
    "1.2.840.10008.5.1.4.1.1.78.6",    # SpectaclePrescriptionReportStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.3", # StereometricRelationshipStorage
    "1.2.840.10008.5.1.4.1.1.78.4",    # SubjectiveRefractionMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.68.1",    # SurfaceScanMeshStorage
    "1.2.840.10008.5.1.4.1.1.68.2",    # SurfaceScanPointCloudStorage
    "1.2.840.10008.5.1.4.1.1.66.5",    # SurfaceSegmentationStorage
    "1.2.840.10008.5.1.4.1.1.9.1.1",   # TwelveLeadECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.78.5",    # VisualAcuityMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.11.5",    # XAXRFGrayscaleSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.88.67",   # XRayRadiationDoseSRStorage
    ## retired but still in use
    "1.2.840.10008.5.1.4.1.1.9",       # StandaloneCurveStorage
    "1.2.840.10008.5.1.4.1.1.10",      # StandaloneModalityLUTStorage
    "1.2.840.10008.5.1.4.1.1.8",       # StandaloneOverlayStorage
    "1.2.840.10008.5.1.4.1.1.129",     # StandalonePETCurveStorage
    "1.2.840.10008.5.1.4.1.1.11",      # StandaloneVOILUTStorage
    "1.2.840.10008.5.1.1.27",          # StoredPrintStorage
]

_all_transfer_syntaxes = _uncompressed_transfer_syntaxes + _compressed_transfer_syntaxes

StoragePresentationContexts = (
    [build_context(uid, _all_transfer_syntaxes) for uid in sorted(_image_storage)]
    + [build_context(uid, _uncompressed_transfer_syntaxes) for uid in sorted(_non_image_storage)]
)
"""Pre-built presentation contexts for Storage SOP Classes.

Image SOP classes are offered with both compressed and uncompressed transfer
syntaxes.  Non-image SOP classes (SR, waveforms, raw data, presentation
states, etc.) are offered with only uncompressed transfer syntaxes to prevent
the SCP from negotiating a compressed TS it cannot actually use for non-pixel
data.
"""

assert len(StoragePresentationContexts) <= 120
