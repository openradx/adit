declare module "dcmjs" {
  export interface dataSet {
    [tag: string]: {
      Value: any;
      vr: string;
    };
  }

  interface nameMap {
    [key: string]: {
      name: string;
      tag: string;
      value: string;
      vr: string;
      vm: string;
    };
  }

  interface dictionary {
    [key: string]: {
      tag: string;
      vr: string;
      name: string;
      vm: string;
      version: string;
    };
  }

  // Add namespace as dcmjs exports some stuff inside a data object,
  // see https://github.com/dcmjs-org/dcmjs/blob/master/src/index.js
  declare namespace data {
    export class DicomDict {
      constructor(meta: object);
      [key: string]: dataSet;
      meta: dataSet;
      dict: dataSet;
      upsertTag(tag: string, vr: string, values: string | object);
    }

    export class DicomMessage {
      static readFile(buffer: ArrayBufferLike): DicomDict;
    }

    export class DicomMetaDictionary {
      static nameMap: nameMap;
      static dictionary: dictionary;
      static punctuateTag(rawTag: string): string;
      static unpunctuateTag(tag: string): string;
      /** converts from DICOM JSON Model dataset to a natural dataset
       * - sequences become lists
       * - single element lists are replaced by their first element,
       *     with single element lists remaining lists, but being a
       *     proxy for the child values, see addAccessors for examples
       * - object member names are dictionary, not group/element tag
       */
      // static naturalizeDataset(dataset: dataSet): { _vrMap: any };
      // static denaturalizeValue(naturalValue: any): any;
      // static denaturalizeDataset(dataset: dataSet, nameMap?: any): any;
      static uid(): string;
      static date(): string;
      static time(): string;
      static dateTime(): string;
    }

    export class Tag {
      constructor(value: object);
      static fromString(str: string): Tag;
      static fromPString(str: string): Tag;
      group(): number;
      toString(): string;
      toCleanString(): string;
      is(t: string): boolean;
      element(): number;
      isPixelDataTag(): boolean;
      isPrivateCreator(): boolean;
    }
  }
}
