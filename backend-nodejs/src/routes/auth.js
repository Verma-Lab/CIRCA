// backend/src/routes/auth.js
'use strict';

import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import firestore from '../services/db/firestore.js';
import multer from 'multer';

import cloudStorageService from '../services/storage/cloudStorage.js';

const router = express.Router();

// Your existing register route
// router.post('/register', async (req, res) => {
//   try {
//     const { email, password, name } = req.body;
    
//     // Hash password
//     const hashedPassword = await bcrypt.hash(password, 10);
    
//     // Create user
//     const user = await firestore.createUser({
//       email,
//       password: hashedPassword,
//       name,
//       apiKey: uuidv4()
//     });

//     // Generate token
//     const token = jwt.sign(
//       { userId: user.id },
//       process.env.JWT_SECRET,
//       { expiresIn: '24h' }
//     );

//     res.status(201).json({ token, user: { id: user.id, email, name } });
//   } catch (error) {
//     res.status(400).json({ error: error.message });
//   }
// });
// backend/src/routes/auth.js
const memoryStorage = multer.memoryStorage();
const upload = multer({ storage: memoryStorage });

/**
 * POST /register
 * Expects multipart/form-data:
 *  - Fields: email, password, name, plan, profession, expertise (as JSON?), experience, bio
 *  - File: avatar (optional, to upload to GCS)
 */
// router.post('/register', upload.single('avatar'), async (req, res) => {
//   try {
//     const {
//       email,
//       password,
//       name,
//       plan = 'free',
//       profession,
//       expertise,
//       experience,
//       bio,
//     } = req.body;

//     // Required fields check
//     if (!email || !password || !name) {
//       return res.status(400).json({
//         error: 'Missing required fields: email, password, or name.',
//       });
//     }

//     // Parse `expertise` if JSON was sent
//     let parsedExpertise = [];
//     if (expertise) {
//       try {
//         parsedExpertise = JSON.parse(expertise);
//       } catch (e) {
//         parsedExpertise = [expertise];
//       }
//     }

//     // Hash password
//     const hashedPassword = await bcrypt.hash(password, 10);

//     // Upload avatar to GCS if file is provided
//     let avatarUrl = null;
//     if (req.file) {
//       console.log('Uploading avatar to GCS...');
//       const uploadResult = await cloudStorageService.uploadImage(req.file, 'avatars');
//       avatarUrl = uploadResult.publicUrl; // Signed URL
//       console.log('Signed URL for avatar:', avatarUrl);
//     }

//     // Create user in Firestore
//     const user = await firestore.createUser({
//       email,
//       password: hashedPassword,
//       name,
//       plan,
//       apiKey: uuidv4(),
//       profession,
//       expertise: parsedExpertise,
//       experience,
//       bio,
//       avatar: avatarUrl, // Save the signed URL
//       profileCompleted: true,
//     });

//     // Generate JWT
//     const token = jwt.sign(
//       { userId: user.id },
//       process.env.JWT_SECRET, // Set in .env
//       // { expiresIn: '24h' }
//     );

//     // Send response
//     res.status(201).json({
//       token,
//       user: {
//         id: user.id,
//         email: user.email,
//         name: user.name,
//         plan: user.plan,
//         profession: user.profession,
//         expertise: user.expertise,
//         experience: user.experience,
//         bio: user.bio,
//         avatar: user.avatar, // e.g. signed URL
//         limits: user.limits,
//         profileCompleted: true,
//       },
//     });
//   } catch (error) {
//     console.error('Error in /register route:', error);
//     res.status(400).json({ error: error.message });
//   }
// });
// backend/src/routes/auth.js
router.post('/register', upload.single('avatar'), async (req, res) => {
  try {
    const {
      email,
      password,
      name,
      plan = 'free',
      accountType,
      organization_id, // Add this line to retrieve organization_id from request
      // Private account fields
      profession,
      expertise,
      experience,
      bio,
      // Company account fields
      companyName,
      industry,
      companySize,
      companyDescription,
    } = req.body;

    // Required fields check
    if (!email || !password || !name) {
      return res.status(400).json({
        error: 'Missing required fields: email, password, or name.',
      });
    }

    // Parse expertise if JSON was sent (for private accounts)
    let parsedExpertise = [];
    if (expertise) {
      try {
        parsedExpertise = JSON.parse(expertise);
      } catch (e) {
        parsedExpertise = [expertise];
      }
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Upload avatar to GCS if file is provided
    let avatarUrl = null;
    if (req.file) {
      console.log('Uploading avatar to GCS...');
      const uploadResult = await cloudStorageService.uploadImage(req.file, 'avatars');
      avatarUrl = uploadResult.publicUrl;
      console.log('Signed URL for avatar:', avatarUrl);
    }

    // Create base user data
    const userData = {
      email,
      password: hashedPassword,
      name,
      plan,
      apiKey: uuidv4(),
      avatar: avatarUrl,
      accountType: accountType || 'private',
      profileCompleted: true,
      organization_id: organization_id || null, // Add organization_id to the user data

    };

    // Add account type specific fields
    if (accountType === 'company') {
      Object.assign(userData, {
        companyName,
        industry,
        companySize,
        companyDescription,
      });
    } else {
      Object.assign(userData, {
        profession,
        expertise: parsedExpertise,
        experience,
        bio,
      });
    }

    // Create user in Firestore
    const user = await firestore.createUser(userData);

    // Generate JWT
    const token = jwt.sign(
      { userId: user.id },
      process.env.JWT_SECRET
    );

    // Prepare response data based on account type
    const responseUserData = {
      id: user.id,
      email: user.email,
      name: user.name,
      plan: user.plan,
      avatar: user.avatar,
      accountType: user.accountType,
      limits: user.limits,
      profileCompleted: true,
      organization_id: user.organization_id, // Include the organization_id in the response

    };

    if (accountType === 'company') {
      Object.assign(responseUserData, {
        companyName: user.companyName,
        industry: user.industry,
        companySize: user.companySize,
        companyDescription: user.companyDescription,
      });
    } else {
      Object.assign(responseUserData, {
        profession: user.profession,
        expertise: user.expertise,
        experience: user.experience,
        bio: user.bio,
      });
    }

    // Send response
    res.status(201).json({
      token,
      user: responseUserData,
    });
  } catch (error) {
    console.error('Error in /register route:', error);
    res.status(400).json({ error: error.message });
  }
});
// Your existing login route
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    // Get user by email
    const users = await firestore.db.collection('users')
      .where('email', '==', email)
      .limit(1)
      .get();
    
    if (users.empty) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const user = { id: users.docs[0].id, ...users.docs[0].data() };
    
    // Check password
    const validPassword = await bcrypt.compare(password, user.password);
    if (!validPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Generate token
    const token = jwt.sign(
      { userId: user.id },
      process.env.JWT_SECRET,
      // { expiresIn: '24h' }
    );

    res.json({
      token,
      user: {
        id: user.id,
        email: user.email,
        name: user.name
      }
    });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// Add new verify endpoint
// router.get('/verify', async (req, res) => {
//   try {
//     const token = req.headers.authorization?.split(' ')[1];
    
//     if (!token) {
//       return res.status(401).json({ error: 'No token provided' });
//     }

//     // Verify the token
//     const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
//     // Get user data to ensure the user still exists
//     const userDoc = await firestore.db.collection('users').doc(decoded.userId).get();
    
//     if (!userDoc.exists) {
//       return res.status(401).json({ error: 'User not found' });
//     }
//     console.log(userDoc)
//     const userData = userDoc.data();
//     res.json({ 
//       valid: true,
//       user: {
//         id: userDoc.id,
//         email: userDoc.data().email,
//         name: userDoc.data().name,
//         plan: userData.plan,
//         limits: userData.limits,
//             // Adding the additional profile fields
//             profession: userData.profession,
//             expertise: userData.expertise,
//             experience: userData.experience,
//             bio: userData.bio,
//             avatar: userData.avatar,
//             profileCompleted: userData.profileCompleted
//       }
//     });
//   } catch (error) {
//     if (error.name === 'JsonWebTokenError') {
//       return res.status(401).json({ error: 'Invalid token' });
//     }
//     // if (error.name === 'TokenExpiredError') {
//     //   return res.status(401).json({ error: 'Token expired' });
//     // }
//     res.status(500).json({ error: 'Verification failed' });
//   }
// });
router.get('/verify', async (req, res) => {
  try {
    const token = req.headers.authorization?.split(' ')[1];
    
    if (!token) {
      return res.status(401).json({ error: 'No token provided' });
    }

    // Verify the token
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
    // Get user data to ensure the user still exists
    const userDoc = await firestore.db.collection('users').doc(decoded.userId).get();
    
    if (!userDoc.exists) {
      return res.status(401).json({ error: 'User not found' });
    }

    const userData = userDoc.data();

    // Base response data
    const responseData = {
      id: userDoc.id,
      email: userData.email,
      name: userData.name,
      plan: userData.plan,
      limits: userData.limits,
      avatar: userData.avatar,
      accountType: userData.accountType || 'private',
      profileCompleted: userData.profileCompleted
    };

    // Add fields based on account type
    if (userData.accountType === 'company') {
      Object.assign(responseData, {
        companyName: userData.companyName,
        industry: userData.industry,
        companySize: userData.companySize,
        companyDescription: userData.companyDescription
      });
    } else {
      Object.assign(responseData, {
        profession: userData.profession,
        expertise: userData.expertise,
        experience: userData.experience,
        bio: userData.bio
      });
    }

    res.json({ 
      valid: true,
      user: responseData
    });
  } catch (error) {
    if (error.name === 'JsonWebTokenError') {
      return res.status(401).json({ error: 'Invalid token' });
    }
    res.status(500).json({ error: 'Verification failed' });
  }
});

// Add these routes to your auth.js

// Update profile endpoint
// Update the update-profile endpoint in auth.js
// backend/src/routes/auth.js - update profile endpoint

// router.put('/update-profile', upload.single('avatar'), async (req, res) => {
//   try {
//     const token = req.headers.authorization?.split(' ')[1];
//     if (!token) {
//       return res.status(401).json({ error: 'No token provided' });
//     }

//     // Verify the token
//     const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
//     // Get all possible fields to update
//     const { 
//       name,
//       email,
//       profession,
//       expertise,
//       experience,
//       bio,
//       plan 
//     } = req.body;
    
//     // Create update object with only the fields that are provided
//     const updateData = {
//       ...(name && { name }),
//       ...(email && { email }),
//       ...(profession && { profession }),
//       ...(expertise && { expertise: typeof expertise === 'string' ? JSON.parse(expertise) : expertise }),
//       ...(experience && { experience }),
//       ...(bio && { bio }),
//       ...(plan && { plan }),
//       profileCompleted: true
//     };
//     console.log(req.file)
//     // If file was uploaded, add the avatar URL
//     if (req.file) {
//       console.log('Uploading avatar to GCS...');
//       const uploadResult = await cloudStorageService.uploadImage(req.file, 'avatars');
//       updateData.avatar = uploadResult.publicUrl;
//       console.log('New avatar URL:', uploadResult.publicUrl);
//     }

//     // If updating plan, also update limits
//     if (plan) {
//       updateData.limits = firestore.getPlanLimits(plan);
//     }

//     // Update user document
//     const userRef = firestore.db.collection('users').doc(decoded.userId);
    
//     // If email is being updated, check for duplicates
//     if (email) {
//       const existingUsers = await firestore.db.collection('users')
//         .where('email', '==', email)
//         .where('id', '!=', decoded.userId)
//         .get();
      
//       if (!existingUsers.empty) {
//         return res.status(400).json({ error: 'Email already in use' });
//       }
//     }

//     await userRef.update(updateData);

//     // Get updated user data
//     const userDoc = await userRef.get();
//     const userData = userDoc.data();

//     res.json({
//       user: {
//         id: userDoc.id,
//         email: userData.email,
//         name: userData.name,
//         profession: userData.profession,
//         expertise: userData.expertise,
//         experience: userData.experience,
//         bio: userData.bio,
//         avatar: userData.avatar,
//         plan: userData.plan,
//         limits: userData.limits,
//         profileCompleted: userData.profileCompleted
//       }
//     });
//   } catch (error) {
//     console.error('Error in update-profile:', error);
//     if (error.name === 'JsonWebTokenError') {
//       return res.status(401).json({ error: 'Invalid token' });
//     }
//     res.status(500).json({ error: error.message });
//   }
// });
router.put('/update-profile', upload.single('avatar'), async (req, res) => {
  try {
    const token = req.headers.authorization?.split(' ')[1];
    if (!token) {
      return res.status(401).json({ error: 'No token provided' });
    }

    // Verify the token
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
    // Get user data to check account type
    const userDoc = await firestore.db.collection('users').doc(decoded.userId).get();
    const userData = userDoc.data();
    
    // Get all possible fields to update
    const { 
      name,
      email,
      plan,
      // Private account fields
      profession,
      expertise,
      experience,
      bio,
      // Company account fields
      companyName,
      industry,
      companySize,
      companyDescription
    } = req.body;
    
    // Create base update object
    const updateData = {
      ...(name && { name }),
      ...(email && { email }),
      ...(plan && { plan }),
      profileCompleted: true
    };

    // Add account type specific fields
    if (userData.accountType === 'company') {
      Object.assign(updateData, {
        ...(companyName && { companyName }),
        ...(industry && { industry }),
        ...(companySize && { companySize }),
        ...(companyDescription && { companyDescription })
      });
    } else {
      Object.assign(updateData, {
        ...(profession && { profession }),
        ...(expertise && { 
          expertise: typeof expertise === 'string' ? JSON.parse(expertise) : expertise 
        }),
        ...(experience && { experience }),
        ...(bio && { bio })
      });
    }

    // Handle avatar upload
    if (req.file) {
      console.log('Uploading avatar to GCS...');
      const uploadResult = await cloudStorageService.uploadImage(req.file, 'avatars');
      updateData.avatar = uploadResult.publicUrl;
      console.log('New avatar URL:', uploadResult.publicUrl);
    }

    // Update limits if plan is changing
    if (plan) {
      updateData.limits = firestore.getPlanLimits(plan);
    }

    // Check for email duplicates if email is being updated
    if (email) {
      const existingUsers = await firestore.db.collection('users')
        .where('email', '==', email)
        .where('id', '!=', decoded.userId)
        .get();
      
      if (!existingUsers.empty) {
        return res.status(400).json({ error: 'Email already in use' });
      }
    }

    // Update user document
    const userRef = firestore.db.collection('users').doc(decoded.userId);
    await userRef.update(updateData);

    // Get updated user data
    const updatedDoc = await userRef.get();
    const updatedData = updatedDoc.data();

    // Prepare response data
    const responseData = {
      id: updatedDoc.id,
      email: updatedData.email,
      name: updatedData.name,
      plan: updatedData.plan,
      limits: updatedData.limits,
      avatar: updatedData.avatar,
      accountType: updatedData.accountType,
      profileCompleted: updatedData.profileCompleted
    };

    // Add account type specific fields to response
    if (updatedData.accountType === 'company') {
      Object.assign(responseData, {
        companyName: updatedData.companyName,
        industry: updatedData.industry,
        companySize: updatedData.companySize,
        companyDescription: updatedData.companyDescription
      });
    } else {
      Object.assign(responseData, {
        profession: updatedData.profession,
        expertise: updatedData.expertise,
        experience: updatedData.experience,
        bio: updatedData.bio
      });
    }

    res.json({ user: responseData });
  } catch (error) {
    console.error('Error in update-profile:', error);
    if (error.name === 'JsonWebTokenError') {
      return res.status(401).json({ error: 'Invalid token' });
    }
    res.status(500).json({ error: error.message });
  }
});
// Change password endpoint
router.put('/change-password', async (req, res) => {
  try {
    const token = req.headers.authorization?.split(' ')[1];
    if (!token) {
      return res.status(401).json({ error: 'No token provided' });
    }

    // Verify the token
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
    const { currentPassword, newPassword } = req.body;
    
    // Get user data
    const userDoc = await firestore.db.collection('users').doc(decoded.userId).get();
    if (!userDoc.exists) {
      return res.status(404).json({ error: 'User not found' });
    }

    const userData = userDoc.data();

    // Verify current password
    const validPassword = await bcrypt.compare(currentPassword, userData.password);
    if (!validPassword) {
      return res.status(401).json({ error: 'Current password is incorrect' });
    }

    // Hash new password
    const hashedPassword = await bcrypt.hash(newPassword, 10);

    // Update password
    await userDoc.ref.update({
      password: hashedPassword
    });

    res.json({ message: 'Password updated successfully' });
  } catch (error) {
    if (error.name === 'JsonWebTokenError') {
      return res.status(401).json({ error: 'Invalid token' });
    }
    res.status(500).json({ error: error.message });
  }
});

export default router;