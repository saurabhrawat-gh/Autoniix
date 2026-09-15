import { hash, verify } from "@node-rs/argon2";

export class PasswordManager {
  static async hashPassword(password: string): Promise<string> {
    try {
      return await hash(password, {
        memoryCost: 19456,
        timeCost: 2,
        outputLen: 32,
        parallelism: 1,
      });
    } catch (error) {
      throw new Error("Password hashing failed");
    }
  }

  static async verifyPassword(password: string, hash: string): Promise<boolean> {
    try {
      return await verify(hash, password);
    } catch (error) {
      return false;
    }
  }
}
