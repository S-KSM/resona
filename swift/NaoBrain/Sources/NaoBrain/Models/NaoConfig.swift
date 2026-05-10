import Foundation

struct NaoConfig: Codable, Equatable {
    var museAddress: String?
    var voiceName: String
    var voiceRate: Int
    var lastSource: String

    enum CodingKeys: String, CodingKey {
        case museAddress = "muse_address"
        case voiceName = "voice_name"
        case voiceRate = "voice_rate"
        case lastSource = "last_source"
    }
}

struct ConfigPatch: Codable {
    var museAddress: String?
    var voiceName: String?
    var voiceRate: Int?
    var lastSource: String?

    enum CodingKeys: String, CodingKey {
        case museAddress = "muse_address"
        case voiceName = "voice_name"
        case voiceRate = "voice_rate"
        case lastSource = "last_source"
    }
}
